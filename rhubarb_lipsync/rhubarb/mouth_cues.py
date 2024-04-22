import logging
import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Callable, Optional, ParamSpec, TypeAlias, TypeVar

from rhubarb_lipsync.rhubarb.mouth_shape_info import MouthShapeInfo, MouthShapeInfos

log = logging.getLogger(__name__)


def time2frame_float(time: float, fps: int, fps_base=1.0) -> float:
    assert fps > 0 and fps_base > 0, f"Can't convert to frame when fps is {fps}/{fps_base}"
    frame_float = time * fps / fps_base
    return round(frame_float, 7)  # Round when very close to an integer value to gain better frame<=>time consistency


def time2frame_nearest(time: float, fps: int, fps_base=1.0) -> int:
    """Convert time in seconds to nearest int frame number"""
    return int(round(time2frame_float(time, fps, fps_base)))


def time2frame_up(time: float, fps: int, fps_base=1.0) -> int:
    """Convert time in seconds to nearest bigger or equal int frame number"""
    return int(math.ceil(time2frame_float(time, fps, fps_base)))


def time2frame_down(time: float, fps: int, fps_base=1.0) -> int:
    """Convert time in seconds to nearest smaller or equal int frame number"""
    return int(math.floor(time2frame_float(time, fps, fps_base)))


def frame2time(frame: float, fps: int, fps_base=1.0) -> float:
    """Converts frame number to time in seconds"""
    assert fps > 0 and fps_base > 0, f"Can't convert to time when fps is {fps}/{fps_base}"
    return frame * fps_base / fps


def duration_scale_rate(current_len: float, desired_len: float, scale_min: float, scale_max: float) -> float:
    """Returns the scale factor so the `current_len` matches the `desired_len` as close as possible."""
    assert current_len != 0, "Can't scale zero length duration"
    scale = desired_len / current_len
    scale = max(scale_min, min(scale, scale_max))
    return scale


def duration_scale(current_len: float, desired_len: float, scale_min: float, scale_max: float) -> float:
    return current_len * duration_scale_rate(current_len, desired_len, scale_min, scale_max)


T = TypeVar('T')
P = ParamSpec('P')
WrappedFuncDeco: TypeAlias = Callable[[Callable[P, T]], Callable[P, T]]


def docstring_from(copy_func: Callable[..., Any]) -> WrappedFuncDeco[P, T]:
    """Copies the doc string of the given function to another."""

    def wrapped(func: Callable[P, T]) -> Callable[P, T]:
        func.__doc__ = copy_func.__doc__
        return func

    return wrapped


@dataclass
class FrameConfig:
    """Wraps fields needed to map time (of a cue) to frames"""

    fps: int
    fps_base: float = 1.0
    offset: int = 0
    subframes: bool = True

    @property
    def fps_base_offset(self) -> tuple[int, float, int]:
        return (self.fps, self.fps_base, self.offset)


class MouthCue:
    """Instance of a mouth shape at specific time-interval."""

    def __init__(self, key: str, start: float, end: float) -> None:
        self.key = key
        self.start = float(start)
        self.end = float(end)

    @staticmethod
    def of_json(cue_json: dict) -> 'MouthCue':
        return MouthCue(cue_json["value"], cue_json["start"], cue_json["end"])

    def to_json(self) -> dict:
        return {
            "start": f"{self.start:.2f}",
            "end": f"{self.end:.2f}",
            "value": self.key,
        }

    @cached_property
    def info(self) -> MouthShapeInfo:
        return MouthShapeInfos[self.key].value

    @cached_property
    def key_index(self) -> int:
        return MouthShapeInfos.key2index(self.key)

    def get_start_frame(self, fps: int, fps_base=1.0, offset=0) -> int:
        """Closest whole frame number of the cue start time"""
        return time2frame_nearest(self.start, fps, fps_base) + offset

    def get_start_frame_float(self, fps: int, fps_base=1.0, offset=0) -> float:
        """Exact decimal frame number of the cue start time"""
        return time2frame_float(self.start, fps, fps_base) + offset

    def get_end_frame(self, fps: int, fps_base=1.0, offset=0) -> int:
        """Closest whole frame number of the cue end time"""
        return time2frame_nearest(self.end, fps, fps_base) + offset

    def get_end_frame_float(self, fps: int, fps_base=1.0, offset=0) -> float:
        """Exact decimal frame number of the cue stop time"""
        return time2frame_float(self.end, fps, fps_base) + offset

    def get_start_subframe(self, fps: int, fps_base=1.0, offset=0) -> tuple[int, float]:
        """Whole frame (without rounding) + decimal part (between 0.0 and 1.0) of the exact frame number."""
        f, i = math.modf(self.get_start_frame_float(fps, fps_base, offset))
        return int(i), f

    @property
    def duration(self) -> float:
        return self.end - self.start

    def get_duration_frames(self, fps: int, fps_base=1.0) -> float:
        return time2frame_float(self.duration, fps, fps_base)

    def __eq__(self, other) -> bool:
        if not isinstance(other, MouthCue):
            # https://stackoverflow.com/questions/1227121/compare-object-instances-for-equality-by-their-attributes
            return NotImplemented  # type: ignore

        def c(a: float, b: float) -> bool:
            return math.isclose(a, b, abs_tol=0.001)

        o: MouthCue = other
        return self.key == o.key and c(self.start, o.start) and c(self.end, o.end)

    def __repr__(self) -> str:
        return f"'{self.key}' {self.start:0.2f}-{self.end:0.2f}"


@dataclass
class MouthCueFrames:
    """Additional wrapper on top of Cues which handles frame related calculations"""

    cue: MouthCue
    frame_cfg: FrameConfig = field(repr=False)
    blend_in: float = field(default=0, repr=False)

    @docstring_from(MouthCue.get_start_frame_float)  # type: ignore[misc]
    @property
    def start_frame(self) -> int:
        return self.cue.get_start_frame(*self.frame_cfg.fps_base_offset)

    @docstring_from(MouthCue.get_start_frame_float)  # type: ignore[misc]
    @property
    def start_frame_float(self) -> float:
        return self.cue.get_start_frame_float(*self.frame_cfg.fps_base_offset)

    @docstring_from(MouthCue.get_start_subframe)  # type: ignore[misc]
    @property
    def start_subframe(self) -> tuple[int, float]:
        return self.cue.get_start_subframe(*self.frame_cfg.fps_base_offset)

    @property
    def start_frame_right(self) -> int:
        """Start time rounded up to the closest integer frame number"""
        c = self.frame_cfg
        return time2frame_up(self.cue.start, c.fps, c.fps_base) + c.offset

    @property
    def start_frame_left(self) -> int:
        """Start time rounded down to the closest integer frame number"""
        c = self.frame_cfg
        return time2frame_down(self.cue.start, c.fps, c.fps_base) + c.offset

    @property
    def pre_start_float(self) -> float:
        """Start time with the blend-in included. This time is few fractions of second before the start time"""
        return self.cue.start - self.blend_in

    @property
    def pre_start_frame_float(self) -> float:
        return self.start_frame_float - self.blend_in_frames

    @docstring_from(MouthCue.get_end_frame)  # type: ignore[misc]
    @property
    def end_frame(self) -> int:
        return self.cue.get_end_frame(*self.frame_cfg.fps_base_offset)

    @docstring_from(MouthCue.get_end_frame_float)  # type: ignore[misc]
    @property
    def end_frame_float(self) -> float:
        return self.cue.get_end_frame_float(*self.frame_cfg.fps_base_offset)

    @property
    def end_frame_right(self) -> int:
        """End time rounded up to the closest integer frame number"""
        c = self.frame_cfg
        return time2frame_up(self.cue.end, c.fps, c.fps_base) + c.offset

    @property
    def end_frame_left(self) -> int:
        """End time rounded down to the closest integer frame number"""
        c = self.frame_cfg
        return time2frame_down(self.cue.end, c.fps, c.fps_base) + c.offset

    @property
    def intersects_frame(self) -> bool:
        """Whether the cue duration is long enough and/or placed so there is an integer frame number
        intersecting the cue duration interval. When false there this no intersection with a frame at all and a cue would not be visible (outside NLA)"""
        s = self.start_frame_right
        e = self.end_frame_left
        return bool(e - s >= 0)  # The cue duration is sorter than a single frame duration and is placed inbetween two frames

    @property
    def offset_seconds(self) -> float:
        c = self.frame_cfg
        return frame2time(c.offset, c.fps, c.fps_base)

    @property
    def duration_frames(self) -> int:
        return int(math.ceil(self.end_frame_float - self.start_frame_float))

    @property
    def duration_frames_float(self) -> float:
        return self.end_frame_float - self.start_frame_float

    @property
    def start_time_str(self) -> str:
        return f"{self.cue.start+self.offset_seconds:0.2f}"

    @property
    def start_frame_str(self) -> str:
        if self.frame_cfg.subframes:
            return f"{self.start_frame_float:0.2f}"
        return f"{self.start_frame}"

    @property
    def end_time_str(self) -> str:
        return f"{self.end_frame+self.offset_seconds:0.2f}"

    @property
    def end_frame_str(self) -> str:
        if self.frame_cfg.subframes:
            return f"{self.end_frame_float:0.2f}"
        return f"{self.end_frame}"

    @property
    def blend_out_frames(self) -> float:
        # Blend-out starts right after the cue hits a whole frame number down to the cue end
        c = self.frame_cfg
        return self.end_frame_float + self.blend_in_frames - self.start_frame_right

    @property
    def blend_in_frames(self) -> float:
        # Blend-in starts slightly before the actual cue start (which is pre-shifted to the left by the blend-in value).
        # It can also be shortened via optimization when previous cue is very short to make sure previous cue is prononuced well
        c = self.frame_cfg
        return time2frame_float(self.blend_in, c.fps, c.fps_base)

    @property
    def duration_frames_str(self) -> str:
        if self.frame_cfg.subframes:
            return f"{self.duration_frames_float:0.2f}"
        return f"{self.duration_frames}"

    @property
    def duration_str(self) -> str:
        return f"{self.cue.duration:0.2f}"


@dataclass
class CueProcessor:
    """Holds and processes the list of detected Mouth cues before they are baked."""

    frame_cfg: FrameConfig
    cue_frames: list[MouthCueFrames]

    @docstring_from(frame2time)  # type: ignore[misc]
    def frame2time(self, frame: float) -> float:
        return frame2time(frame - self.frame_cfg.offset, self.frame_cfg.fps, self.frame_cfg.fps_base)

    @docstring_from(time2frame_float)  # type: ignore[misc]
    def time2frame_float(self, t: float) -> float:
        return time2frame_float(t, self.frame_cfg.fps, self.frame_cfg.fps_base) + self.frame_cfg.offset

    def trim_long_cues(self, max_dur: float) -> int:
        modified = 0
        for cf in self.cue_frames:
            d = cf.cue.duration
            if cf.cue.key == 'X':
                continue  # Don't trim X (silence)
            if d <= max_dur:
                continue
            modified += 1
            cf.cue.end = cf.cue.start + max_dur
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
                skipped += 1  # The new end would match the start frame rounded up. So there wouldn't be and blend-out section
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

    def optimize_cues(self, min_cue_duration=0.2, blend_in_time=0.02) -> str:
        steps = [
            (lambda: self.trim_long_cues(min_cue_duration), "ends trimmed"),
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


if __name__ == '__main__':
    c = MouthCue("A", 1, 2)
    cfg = FrameConfig(60)
    cue_frames = MouthCueFrames(c, cfg)
    help(cue_frames)
    cue_frames

    # for a in MouthShapeInfos.__members__.values():
    #     print(a.value)
    #     print(a.value.description)
    # print(MouthCue('A', 1, 2).info.description)

    print("Done")
