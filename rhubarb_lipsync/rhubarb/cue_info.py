import textwrap
from enum import Enum


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
