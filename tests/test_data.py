from pathlib import Path

test_data_path=Path(__file__).parent / "data"

assert test_data_path.exists()
assert test_data_path.is_dir()


snd_cs_female_o_a = {
    "snd_file_path": test_data_path / "cs_female_o_a.ogg"
}

snd_en_male_watchingtv = {
    "snd_file_path": test_data_path / "en_male_watchingtv.ogg"
}
