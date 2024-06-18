import json
import os
import pathlib
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path


@dataclass
class BlenderSetup:
    root_path: Path = field(default_factory=lambda: Path(tempfile.mkdtemp(prefix="blenderFresh_")))
    target_platform: str = field(default_factory=lambda: platform.system())
    blender_ver: str = "4.2"
    addon_src: Path = Path(pathlib.Path(__file__).parent.parent)

    @cached_property
    def user_dir(self) -> Path:
        return self.root_path / "blender" / self.blender_ver

    @cached_property
    def addons_path(self) -> Path:
        return self.user_dir / "scripts" / "addons"

    @cached_property
    def test_results_path(self) -> Path:
        return self.addons_path / "test_results.json"

    def set_blender_user_data(self) -> None:
        xdg_config_home = self.root_path
        env_var = "BLENDER_USER_RESOURCES" if self.target_platform == "Windows" else "XDG_CONFIG_HOME"
        os.environ[env_var] = str(xdg_config_home)
        # os.environ['TEST_RESULTS_PATH'] = str(self.test_results_path)

    def install_addon(self) -> None:
        self.addons_path.mkdir(parents=True, exist_ok=True)
        target = self.addons_path / "rhubarb_lipsync"
        if not target.exists():
            os.symlink(self.addon_src / "rhubarb_lipsync", target)

    def install_tests(self) -> None:
        test_files = list(self.addon_src.glob("tests/*.py"))
        for test_file in test_files:
            shutil.copy(test_file, self.addons_path)

        data_src = self.addon_src / "tests" / "data"
        data_dst = self.addons_path / "data"
        if data_dst.exists():
            shutil.rmtree(data_dst)
        shutil.copytree(data_src, data_dst)

        aud_file = self.addons_path / "aud.py"
        if aud_file.exists():
            aud_file.unlink()

    def setup_config(self) -> None:
        config_dir = self.user_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

    def run_blender(self) -> None:
        script_path = self.addons_path / "run_within_blender.py"
        # exe = 'blender-4.2'
        exe = 'wine "/var/wine/64loc/drive_c/Program Files/Blender Foundation/Blender 3.5/blender.exe"'
        script = subprocess.check_output(['winepath', '-w', str(script_path)]).decode().strip()
        cmd = f'''{exe} --background --python "{script}"'''
        print(cmd)
        os.system(cmd)

    def verify_result(self) -> None:
        if not self.test_results_path.exists():
            raise FileNotFoundError(f"Test results file not found at {self.test_results_path}")

        with self.test_results_path.open('r') as file:
            test_results = json.load(file)

        total_tests = test_results.get("total_tests", 0)
        total_failed = test_results.get("total_failed", 0)

        if total_failed > 0:
            raise AssertionError(f"There are {total_failed} failed tests.")

        if total_tests < 44:
            raise AssertionError(f"Total tests are {total_tests}, expected at least 44 tests, seems some were skip")

        print("All checks passed.")

    def install_and_run(self) -> None:
        self.setup_config()
        self.install_addon()
        self.install_tests()
        self.set_blender_user_data()
        if self.test_results_path.exists():
            self.test_results_path.unlink()
        self.run_blender()
        self.verify_result()


if __name__ == "__main__":
    # setup = BlenderSetup(root_path=Path("/tmp/work/fresh2"), )
    setup = BlenderSetup(root_path=Path("/tmp/work/freshWin"), target_platform="Windows", blender_ver="3.5")
    # setup = BlenderSetup(root_path=Path("/tmp/work/fresh"), target_platform="Linux", blender_ver="4.2")
    setup.install_and_run()
