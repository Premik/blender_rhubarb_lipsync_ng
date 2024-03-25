import math
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, ParamSpec, TypeAlias, TypeVar

from rhubarb_lipsync.rhubarb.mouth_shape_info import MouthShapeInfo, MouthShapeInfos


def time2frame_float(time: float, fps: int, fps_base=1.0) -> float:
    assert fps > 0 and fps_base > 0, f"Can't convert to frame when fps is {fps}/{fps_base}"
    return time * fps / fps_base


def time2frame(time: float, fps: int, fps_base=1.0) -> int:
    return int(round(time2frame_float(time, fps, fps_base)))


def frame2time(frame: float, fps: int, fps_base=1.0) -> float:
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
        """Whole frame number of the cue start time"""
        return time2frame(self.start, fps, fps_base) + offset

    def get_start_frame_float(self, fps: int, fps_base=1.0, offset=0) -> float:
        """Exact decimal frame number of the cue start time"""
        return time2frame_float(self.start, fps, fps_base) + offset

    def get_end_frame(self, fps: int, fps_base=1.0, offset=0) -> int:
        """Whole frame number of the cue end time"""
        return time2frame(self.end, fps, fps_base) + offset

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
    frame_cfg: FrameConfig

    @docstring_from(MouthCue.get_start_frame_float)  # type: ignore[misc]
    @property
    def start_frame(self) -> int:
        return self.cue.get_start_frame(*self.frame_cfg.fps_base_offset)

    @docstring_from(MouthCue.get_start_frame_float)  # type: ignore[misc]
    @property
    def start_frame_float(self) -> float:
        return self.cue.get_start_frame_float(*self.frame_cfg.fps_base_offset)

    @docstring_from(MouthCue.get_end_frame)  # type: ignore[misc]
    @property
    def end_frame(self) -> int:
        return self.cue.get_end_frame(*self.frame_cfg.fps_base_offset)

    @docstring_from(MouthCue.get_end_frame_float)  # type: ignore[misc]
    @property
    def end_frame_float(self) -> float:
        return self.cue.get_end_frame_float(*self.frame_cfg.fps_base_offset)

    @docstring_from(MouthCue.get_start_subframe)  # type: ignore[misc]
    @property
    def start_subframe(self) -> tuple[int, float]:
        return self.cue.get_start_subframe(*self.frame_cfg.fps_base_offset)

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
        return f"{self.start_frame+self.offset_seconds:0.2f}"

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

    def trim_long_cues(self, max_dur: float) -> int:
        trimmed = 0
        for cf in self.cue_frames:
            d = cf.cue.duration
            if d <= max_dur:
                continue
            trimmed += 1
            cf.cue.end = cf.cue.start + max_dur
        # if trimmed > 0:
        #     self.rlog.info(f"Trimmed {trimmed} Cues as they were too long.")
        return trimmed


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
