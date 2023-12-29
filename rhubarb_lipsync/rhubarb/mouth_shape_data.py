import math
from functools import cached_property
from enum import Enum
import textwrap


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


class MouthShapeInfo:
    """Description of a mouth shape. Metadata."""

    def __init__(self, key: str, key_displ: str, short_dest: str = "", description: str = "", extended=False) -> None:
        self.key = key
        self.short_dest = short_dest
        self.description = textwrap.dedent(description)
        self.key_displ = key_displ
        self.extended = extended

    def __str__(self) -> str:
        return f"({self.key})-'{self.short_dest}'"

    def __repr__(self) -> str:
        return f"{self.key}"


class MouthShapeInfos(Enum):
    """All possible mouth shapes. Based on the  https://github.com/DanielSWolf/rhubarb-lip-sync#readme"""

    _all: list[MouthShapeInfo]

    A = MouthShapeInfo(
        'A',
        'Ⓐ',
        'P B M sounds. Closed mouth.',
        '''\
            Closed mouth for the “P”, “B”, and “M” sounds. 
            This is almost identical to the Ⓧ shape, but there is ever-so-slight pressure between the lips.''',
    )
    B = MouthShapeInfo(
        'B',
        'Ⓑ',
        'K S T sounds. Slightly opened mouth.',
        '''\
            Slightly open mouth with clenched teeth. 
            This mouth shape is used for most consonants (“K”, “S”, “T”, etc.). 
            It’s also used for some vowels such as the “EE” sound in bee.''',
    )
    C = MouthShapeInfo(
        'C',
        'Ⓒ',
        'EH AE sounds. Opened mouth.',
        '''\
            Open mouth. This mouth shape is used for vowels like “EH” as in men and “AE” as in bat. 
            It’s also used for some consonants, depending on context.
            This shape is also used as an in-between when animating from Ⓐ or Ⓑ to Ⓓ. 
            So make sure the animations ⒶⒸⒹ and ⒷⒸⒹ look smooth!''',
    )
    D = MouthShapeInfo(
        'D',
        'Ⓓ',
        'A sound. Wide opened mouth.',
        '''\
            Wide open mouth. This mouth shapes is used for vowels like “AA” as in father.''',
    )
    E = MouthShapeInfo(
        'E',
        'Ⓔ',
        'AO ER sounds. Slightly rounded mouth.',
        '''\
            Slightly rounded mouth. This mouth shape is used for vowels like “AO” as in off and “ER” as in bird.
            This shape is also used as an in-between when animating from Ⓒ or Ⓓ to Ⓕ. 
            Make sure the mouth isn’t wider open than for Ⓒ. 
            Both ⒸⒺⒻ and ⒹⒺⒻ should result in smooth animation.''',
    )
    F = MouthShapeInfo(
        'F',
        'Ⓕ',
        'UW OW W sounds. Puckered lips.',
        '''\
            Puckered lips. This mouth shape is used for “UW” as in you, “OW” as in show, and “W” as in way.''',
    )
    G = MouthShapeInfo(
        'G',
        'Ⓖ',
        'F V sounds. Teeth touched lip.',
        '''\
            Upper teeth touching the lower lip for “F” as in for and “V” as in very.
            If your art style is detailed enough, it greatly improves the overall look of the animation.''',
        True,
    )
    H = MouthShapeInfo(
        'H',
        'Ⓗ',
        'L sounds. Tongue raised.',
        '''\
            This shape is used for long “L” sounds, with the tongue raised behind the upper teeth. 
            The mouth should be at least far open as in Ⓒ, but not quite as far as in Ⓓ.
            Depending on your art style and the angle of the head, the tongue may not be visible at all. 
            In this case, there is no point in drawing this extra shape.''',
        True,
    )
    X = MouthShapeInfo(
        'X',
        'Ⓧ',
        'Idle.',
        '''\
            Idle position. This mouth shape is used for pauses in speech. 
            This should be the same mouth drawing you use when your character is walking around without talking. 
            It is almost identical to Ⓐ, but with slightly less pressure between the lips: For Ⓧ, the lips should be closed but relaxed.
            Whether there should be any visible difference between the rest position Ⓧ and the closed 
            talking mouth Ⓐ depends on your art style and personal taste.''',
        True,
    )

    @staticmethod
    def all() -> list[MouthShapeInfo]:
        if not getattr(MouthShapeInfos, '_all', None):
            MouthShapeInfos._all = [m.value for m in MouthShapeInfos.__members__.values()]
        return MouthShapeInfos._all  # type: ignore

    @staticmethod
    def extended() -> list[MouthShapeInfo]:
        return [mi for mi in MouthShapeInfos.all() if mi.extended]

    @staticmethod
    def key2index(key: str) -> int:
        i = ord(key) - ord('A')
        all = MouthShapeInfos.all()
        if i < 0 or i >= len(all):
            return len(all) - 1  # Return the last ('X') for unknown keys
        return i

    @staticmethod
    def index2Info(index: int) -> MouthShapeInfo:
        all = MouthShapeInfos.all()
        if index >= len(all) or index < 0:
            return all[-1]  # Return 'X' for out-of-range indices
        return all[index]


class MouthCue:
    """Instance of a mouth shape at specific time-interval."""

    def __init__(self, key: str, start: float, end: float) -> None:
        self.key = key
        self.start = float(start)
        self.end = float(end)

    @staticmethod
    def of_json(cue_json: dict) -> 'MouthCue':
        return MouthCue(cue_json["value"], cue_json["start"], cue_json["end"])

    @cached_property
    def info(self) -> MouthShapeInfo:
        return MouthShapeInfos[self.key].value

    @cached_property
    def key_index(self) -> int:
        return MouthShapeInfos.key2index(self.key)

    def start_frame(self, fps: int, fps_base=1.0, offset=0) -> int:
        """Whole frame number of the cue start time"""
        return time2frame(self.start, fps, fps_base) + offset

    def start_frame_float(self, fps: int, fps_base=1.0, offset=0) -> float:
        """Exact decimal frame number of the cue start time"""
        return time2frame_float(self.start, fps, fps_base) + offset

    def end_frame(self, fps: int, fps_base=1.0, offset=0) -> int:
        """Whole frame number of the cue end time"""
        return time2frame(self.end, fps, fps_base) + offset

    def end_frame_float(self, fps: int, fps_base=1.0, offset=0) -> float:
        """Exact decimal frame number of the cue stop time"""
        return time2frame_float(self.end, fps, fps_base) + offset

    def start_subframe(self, fps: int, fps_base=1.0, offset=0) -> tuple[int, float]:
        """Whole frame (without rounding) + decimal part (between 0.0 and 1.0) of the exact frame number."""
        f, i = math.modf(self.start_frame_float(fps, fps_base, offset))
        return int(i), f

    @property
    def duration(self) -> float:
        return self.end - self.start

    def duration_frames(self, fps: int, fps_base=1.0) -> float:
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


if __name__ == '__main__':
    for a in MouthShapeInfos.__members__.values():
        print(a.value)
        print(a.value.description)
    print(MouthCue('A', 1, 2).info.description)

    print("Done")
