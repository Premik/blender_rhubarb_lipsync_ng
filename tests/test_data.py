from functools import cached_property
from pathlib import Path

test_data_path=Path(__file__).parent / "data"

assert test_data_path.exists()
assert test_data_path.is_dir()

class SampleData:
    """Test data. Links to a sound file and additional data"""

    def __init__(self, name:str, test_data_path=test_data_path):
        self.name=name
        self.test_data_path=test_data_path

    @cached_property
    def snd_file_path(self):
        return self.test_data_path / f"{self.name}.ogg"

    @cached_property
    def expected_json_path(self):
        return self.test_data_path / f"{self.name}-expected.json"


snd_cs_female_o_a = SampleData("cs_female_o_a")
snd_en_male_watchingtv = SampleData("en_male_watchingtv") 
snd_en_male_electricity = SampleData("en_male_electricity")