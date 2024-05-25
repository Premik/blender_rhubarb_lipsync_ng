from dataclasses import dataclass, field
from typing import Iterable, Optional

from rhubarb_lipsync.rhubarb.mouth_cues import FrameConfig, MouthCue, MouthCueFrames, docstring_from, frame2time, log, time2frame_float


@dataclass
class CueProcessor:
    """Holds and processes the list of detected Mouth cues before they are baked."""

    frame_cfg: FrameConfig
    cue_frames: list[MouthCueFrames] = field(repr=False)
    trim_tolerance: float = 0.05

    @docstring_from(frame2time)  # type: ignore[misc]
    def frame2time(self, frame: float) -> float:
        return frame2time(frame - self.frame_cfg.offset, self.frame_cfg.fps, self.frame_cfg.fps_base)

    @docstring_from(time2frame_float)  # type: ignore[misc]
    def time2frame_float(self, t: float) -> float:
        return time2frame_float(t, self.frame_cfg.fps, self.frame_cfg.fps_base) + self.frame_cfg.offset

    @property
    def pre_start_cue(self) -> MouthCueFrames:
        s = 0
        if self.cue_frames:
            s = self.cue_frames[0].cue.start
        return MouthCueFrames.create_X(self.frame_cfg, s - 10, s)

    def get(self, index) -> MouthCueFrames:
        """Returns CueFrames at the given index while supporting out-of-range indices too
        by providing fake X cues after the range boundary"""
        if index < 0:
            return self.pre_start_cue
        if index >= len(self.cue_frames):
            return self.post_end_cue
        self.cue_frames[index]

    @property
    def post_end_cue(self) -> MouthCueFrames:
        s = 0
        if self.cue_frames:
            s = self.cue_frames[-1].cue.end
        return MouthCueFrames.create_X(self.frame_cfg, s, s + 10)

    @property
    def the_last_cue(self) -> Optional[MouthCueFrames]:
        if not self.cue_frames:
            return None
        return self.cue_frames[-1]

    def find_cues_by_duration(self, min_dur: float = -1, max_dur: float = -1, tol_max: float = 0.05, tol_min: float = 0.001) -> Iterable[MouthCueFrames]:
        """Finds cues with duration shorter than min_dur (-1 to ignore) or longer than max_dur (-1 to ignore).
        The X (silence) is ignored. Only cues which are significatnly (driven by two tolerance params) longer/short are returned"""
        for i, cf in enumerate(list(self.cue_frames)):
            d = cf.cue.duration
            if cf.cue.key == 'X':
                continue  # Ignore X (silence)
            if max_dur > 0 and d <= max_dur + tol_max:
                continue
            if min_dur > 0 and d >= min_dur - tol_min:
                continue
            yield i, cf

    def trim_long_cues(self, max_dur: float, append_x: bool = True) -> int:
        modified = 0
        for i, cf in self.find_cues_by_duration(-1, max_dur, self.trim_tolerance):
            new_end = cf.cue.start + max_dur
            if append_x:
                cf_x = MouthCueFrames.create_X(self.frame_cfg, new_end, cf.cue.end)
                # Insert the new X after the current trimmed X, encountering previous insertions as they shift the indices
                self.cue_frames.insert(i + modified + 1, cf_x)
            cf.cue.end = new_end  # Trim duration

        if modified > 0:
            log.info(f"Trimmed {modified} Cues as they were too long.")
        return modified

    def ensure_frame_intersection(self) -> int:
        """Finds extremly short cues where there is no intersection with a frame and move either start or end to the closest frame time"""
        modified = 0
        for cf in self.cue_frames:
            if cf.intersects_frame:
                continue
            # Cue is in the middle of two frames, find which end is closer to a frame
            d_start = cf.start_frame_float - cf.start_frame_left
            d_end = cf.end_frame_right - cf.end_frame_float
            assert d_start > 0 and d_end > 0
            if d_start < d_end:  # Start is closer, expand the cue start to the left
                cf.cue.start = self.frame2time(cf.start_frame_left)
            else:  # End is closer, expand the cue end to the right
                cf.cue.end = self.frame2time(cf.end_frame_right)
            modified += 1
        if modified > 0:
            log.info(f"Prolonged {modified} Cues as they were too short and would not have been visible.")
        return modified

    def round_ends_down(self) -> int:
        """Rounds down the cue ends to nearest frame on the left. While making sure very
        short cues won't collapse to only-blend-in phase."""
        modified = 0
        skipped = 0
        for cf in self.cue_frames:
            if not cf.intersects_frame:
                skipped += 1  # Too short. Shouldn't happend if the `ensure_frame_intersection` was called first
                continue
            new_end_frame = cf.end_frame_left
            if abs(cf.start_frame_right - new_end_frame) < 0.0001:
                skipped += 1  # The new end would match the start frame rounded up. So there wouldn't be a blend-out section
                continue  # Leave it out as it is still a short Cue which just happend to be crossing a frame
            cf.cue.end = self.frame2time(new_end_frame)
            modified += 1
        if modified > 0:
            log.info(f"Rounded {modified} Cue ends down to whole frame while skipped {skipped} Cues as they were too short.")
        return modified

    def set_blend_in_times(self, blend_in_time: float = 0.04) -> int:
        """Sets blend-in for each Cue. Trim the blend-in length in case it intersects with previous cue's first frame"""
        last_cue_start_frame_time: Optional[float] = None
        shrinked = 0
        for cf in self.cue_frames:
            cf.blend_in = blend_in_time
            if last_cue_start_frame_time is not None:  # Not a first cue
                d = cf.pre_start_float - last_cue_start_frame_time
                if d >= 0:  # The start time including the blend-in is after the previous cue first frame intersection
                    continue
                assert blend_in_time + d >= 0, f"Cue {cf} start overlaps with previous cue. Blend-in time {blend_in_time} + {d} would be negative "
                cf.blend_in = blend_in_time + d  # Shrink the blend-in phase so the previous cue is fully pronounced at its first frame intersection
                shrinked += 1
            last_cue_start_frame_time = self.frame2time(cf.start_frame_right)
        if shrinked > 0:
            log.info(f"Shrinkened {shrinked} Cue blend-in times down to fully prononuce the previous Cue.")
        return shrinked

    def optimize_cues(self, max_cue_duration=0.2, blend_in_time=0.02) -> str:
        steps = [
            (lambda: self.trim_long_cues(max_cue_duration), "ends trimmed"),
            (self.ensure_frame_intersection, "duration enlarged"),
            (self.round_ends_down, "ends rounded to frame"),
            (lambda: self.set_blend_in_times(blend_in_time), "blend-in time shortened"),
        ]
        report = ""
        for s in steps:
            count = s[0]()
            if count > 0:
                report += f" {s[1]}: {count}"
        return report
