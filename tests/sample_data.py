import json
from functools import cached_property
from pathlib import Path
from typing import cast

from bpy.types import Context, Sound

from rhubarb_lipsync.blender import ui_utils
from rhubarb_lipsync.rhubarb.mouth_cues import MouthCue
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbParser

try:
    from bpy.types import Strip  # Since v4.4
except ImportError:  # Fall back to old API
    from bpy.types import SoundSequence as Strip

sample_data_path = Path(__file__).parent / "data"


class SampleData:
    """Test data. Links to a sound file and additional data"""

    def __init__(self, name: str, sample_data_path=sample_data_path) -> None:
        if not sample_data_path.exists():
            raise FileNotFoundError(f"The path '{sample_data_path}' does not exist.")
        if not sample_data_path.is_dir():
            raise NotADirectoryError(f"The path '{sample_data_path}' is not a directory.")
        self.name = name
        self.sample_data_path = sample_data_path

    @cached_property
    def snd_file_path(self) -> Path:
        return self.sample_data_path / f"{self.name}.ogg"

    @cached_property
    def expected_json_path(self) -> Path:
        return self.sample_data_path / f"{self.name}-expected.json"

    @cached_property
    def expected_json(self) -> str:
        with open(self.expected_json_path) as f:
            return f.read()

    @cached_property
    def expected_json_dict(self) -> dict:
        return json.loads(self.expected_json)

    @cached_property
    def expected_cues(self) -> list[MouthCue]:
        json_parsed = RhubarbParser.parse_lipsync_json(self.expected_json)
        return RhubarbParser.lipsync_json2MouthCues(json_parsed)

    def to_sound(self, ctx: Context) -> Sound:
        strips_coll = ui_utils.get_strips_from_sequence_editor(ctx)
        sq = strips_coll.new_sound(self.name, str(self.snd_file_path), 1, 1)
        return cast(Strip, sq).sound

    @staticmethod
    def compare_cues(a_cues: list[MouthCue], b_cues: list[MouthCue]) -> str:
        if len(a_cues) != len(b_cues):
            return f"Lengths don't match \n{a_cues}\n{b_cues}"
        for i, (a, b) in enumerate(zip(a_cues, b_cues)):
            if a != b:
                return f"Cues at position {i} don't match:\n{a}\n{b}"
        return None

    def compare_cues_with_expected(self, b_cues: list[MouthCue]) -> str:
        return SampleData.compare_cues(self.expected_cues, b_cues)


snd_cs_female_o_a = SampleData("cs_female_o_a")
snd_en_male_watchingtv = SampleData("en_male_watchingtv")
snd_en_male_electricity = SampleData("en_male_electricity")
snd_en_femal_3kittens = SampleData("threelittlekittens_01_rountreesmith")
