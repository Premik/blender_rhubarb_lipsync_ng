from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from rhubarb_lipsync.rhubarb.mouth_cues import FrameConfig, MouthCueFrames, frame2time, log, time2frame_float


@dataclass
class CueProcessor:
    """Holds and processes the list of detected Mouth cues before they are baked."""

    frame_cfg: FrameConfig
    cue_frames: list[MouthCueFrames] = field(repr=False)
    trim_tolerance: float = 0.05
    use_extended_shapes: bool = True

    # @docstring_from(frame2time)  # type: ignore[misc]
    def frame2time(self, frame: float) -> float:
        return frame2time(frame - self.frame_cfg.offset, self.frame_cfg.fps, self.frame_cfg.fps_base)

    # @docstring_from(time2frame_float)  # type: ignore[misc]
    def time2frame_float(self, t: float) -> float:
        return time2frame_float(t, self.frame_cfg.fps, self.frame_cfg.fps_base) + self.frame_cfg.offset

    def create_silence_cue(self, start: float, end: float) -> MouthCueFrames:
        if self.use_extended_shapes:
            return MouthCueFrames.create_X(self.frame_cfg, start, end)
        # When not using extended shapes, the A is used instead of X
        return MouthCueFrames.create_A(self.frame_cfg, start, end)

    def is_cue_silence(self, cf: MouthCueFrames) -> bool:
        if self.use_extended_shapes:
            return cf.is_X
        return cf.is_A

    @property
    def pre_start_cue(self) -> MouthCueFrames:
        s = 0.0
        if self.cue_frames:
            s = self.cue_frames[0].cue.start
        return self.create_silence_cue(s - 10, s)

    def __getitem__(self, index) -> MouthCueFrames:
        """Returns CueFrames at the given index while supporting out-of-range indices too
        by providing fake X cues after the range boundary"""
        if index < 0:
            return self.pre_start_cue
        if index >= len(self.cue_frames):
            return self.post_end_cue
        return self.cue_frames[index]

    @property
    def post_end_cue(self) -> MouthCueFrames:
        s = 0.0
        if self.cue_frames:
            s = self.cue_frames[-1].cue.end
        return self.create_silence_cue(s, s + 10)

    @property
    def the_last_cue(self) -> Optional[MouthCueFrames]:
        if not self.cue_frames:
            return None
        return self.cue_frames[-1]

    def find_cues_by_duration(self, min_dur=-1.0, max_dur=-1.0, tol_max=0.05, tol_min=0.001) -> Iterable[tuple[int, MouthCueFrames]]:
        """Finds cues with duration shorter than min_dur (-1 to ignore) or longer than max_dur (-1 to ignore).
        The X (silence) is ignored. Only cues which are significantly (driven by two tolerance params) longer/short are returned"""
        for i, cf in enumerate(list(self.cue_frames)):
            d = cf.cue.duration
            if self.is_cue_silence(cf):
                continue  # Ignore X (silence)
            if max_dur > 0 and d <= max_dur + tol_max:
                continue
            if min_dur > 0 and d >= min_dur - tol_min:
                continue
            yield i, cf

    def trim_long_cues(self, max_dur: float, append_x: bool = True) -> int:
        modified = 0
        for i, cf in self.find_cues_by_duration(-1, max_dur, self.trim_tolerance):
            modified += 1
            new_end = cf.cue.start + max_dur
            if append_x:
                cf_silence = self.create_silence_cue(new_end, cf.cue.end)
                # Insert the new X after the current trimmed X, encountering previous insertions as they shift the indices
                self.cue_frames.insert(i + modified, cf_silence)
            cf.cue.end = new_end  # Trim duration

        if modified > 0:
            log.info(f"Trimmed {modified} Cues as they were too long.")
        return modified

    def merge_double_x(self) -> int:
        modified = 0
        orig_list = list(self.cue_frames)
        for i, cf in enumerate(orig_list):
            if i <= 0:
                continue
            if not self.is_cue_silence(cf):
                continue
            prev_cue = orig_list[i - 1]
            if not self.is_cue_silence(prev_cue):
                continue
            prev_cue.cue.end = cf.cue.end  # Prolong prev X end up to this X end
            removed = self.cue_frames.pop(i - modified)  # Remove the current X
            assert removed == cf
            modified += 1
            prev_cue = cf

        if modified > 0:
            log.info(f"Removed {modified} X-Cues as they duplicate.")
        return modified

    def ensure_frame_intersection(self) -> int:
        """Finds extremely short cues where there is no intersection with a frame and move either start or end to the closest frame time"""
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

    def optimize_cues(self, max_cue_duration=0.2) -> str:
        steps: list[tuple[Callable[[], int], str]] = [
            (lambda: self.trim_long_cues(max_cue_duration), "ends trimmed"),
            (self.ensure_frame_intersection, "duration enlarged"),
            (self.merge_double_x, "double X removed"),
        ]
        report = ""
        for s in steps:
            count = s[0]()
            if count > 0:
                report += f" {s[1]}: {count}"
        return report
