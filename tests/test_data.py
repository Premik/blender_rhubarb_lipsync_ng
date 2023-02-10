import json
from functools import cached_property
from pathlib import Path
from typing import cast

from bpy.types import Context, Sound, SoundSequence

from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandWrapper, RhubarbParser

test_data_path = Path(__file__).parent / "data"

assert test_data_path.exists()
assert test_data_path.is_dir()


class SampleData:
    """Test data. Links to a sound file and additional data"""

    def __init__(self, name: str, test_data_path=test_data_path):
        self.name = name
        self.test_data_path = test_data_path

    @cached_property
    def snd_file_path(self):
        return self.test_data_path / f"{self.name}.ogg"

    @cached_property
    def expected_json_path(self):
        return self.test_data_path / f"{self.name}-expected.json"

    @cached_property
    def expected_json(self) -> list[dict]:
        with open(self.expected_json_path) as f:
            return json.load(f)

    @cached_property
    def expected_cues(self) -> list[MouthCue]:
        return RhubarbParser.lipsync_json2MouthCues(self.expected_json)

    def to_sound(self, ctx: Context) -> Sound:
        se = ctx.scene.sequence_editor
        sq = se.sequences.new_sound(self.name, str(self.snd_file_path), 1, 1)
        return cast(SoundSequence, sq).sound


snd_cs_female_o_a = SampleData("cs_female_o_a")
snd_en_male_watchingtv = SampleData("en_male_watchingtv")
snd_en_male_electricity = SampleData("en_male_electricity")
