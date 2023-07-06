import re
from functools import cached_property
from pathlib import Path

from config import project_cfg, rhubarb_cfg
import os
import zipfile
import shutil
from rhubarb_bin import RhubarbBinary
import pathlib


def dist_zip_name(platform: str, ver: str) -> str:
    return f"rhubarb_lipsync_ng-{platform}-{ver}"


def clean_temp_files_at(start_path: Path) -> int:
    # https://stackoverflow.com/questions/28991015/python3-project-remove-pycache-folders-and-pyc-files
    deleted = 0
    for p in start_path.rglob('*.py[co]'):
        p.unlink()
        deleted += 1
    for p in start_path.rglob('__pycache__'):
        p.rmdir()
        deleted += 1
    return deleted


class PackagePlugin:
    """Package (zip) project for the distribution"""

    # 'version': (4, 0, 0),
    bl_info_version_pattern = r'''['"]version["']\s*:\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)'''
    bl_info_version_rx = re.compile(f"(.*)({bl_info_version_pattern})(.*)", re.DOTALL)
    main_package_name = 'rhubarb_lipsync'

    def __init__(self, cfg: dict) -> None:
        assert cfg and cfg["project"]
        self.cfg = cfg

    @property
    def version_str(self) -> str:
        return self.cfg["project"]["version"]

    @cached_property
    def version_tuple(self) -> tuple[int, int, int]:
        t = tuple([int(p) for p in self.version_str.split(".")])
        assert len(t) == 3, f"Unexpected version string. Expect 3 digits. Got '{self.version_str}'"
        return t  # type: ignore

    @cached_property
    def project_dir(self) -> Path:
        return Path(__file__).parents[1]

    @cached_property
    def main__init__(self) -> Path:
        return self.project_dir / PackagePlugin.main_package_name / "__init__.py"

    @cached_property
    def dist_dir(self) -> Path:
        return self.project_dir / "dist"

    def update_bl_info_version(self) -> None:
        p = self.main__init__
        print(f"Updating version string to '{self.version_str}' in the {p}")
        assert p.exists(), f"The {p} doesn't exists "
        with open(p, 'r', encoding='utf-8') as s:
            text = s.read()
        m = PackagePlugin.bl_info_version_rx.match(text)
        assert m is not None, f"Failed to find bl_info version string in the {p}. Pattern\n{PackagePlugin.bl_info_version_rx}"
        new_ver = f"'version': {self.version_tuple}"
        text = f"{m.groups()[0]}{new_ver}{m.groups()[2]}"

        with open(p, 'w', encoding='utf-8') as s:
            s.write(text)

    def clean_temp_files(self) -> None:
        d = clean_temp_files_at(self.project_dir)
        print(f"Deleted {d} temp/cache files/dirs from the {self.project_dir}")

    def zip_dist(self, platform: str) -> None:
        """Creates the zip for distribution. Assumes the correct binaries are already deployed in the bin_dir subfolder"""
        zip = self.dist_dir / dist_zip_name(platform, self.version_str)
        # https://stackoverflow.com/questions/1855095/how-to-create-a-zip-archive-of-a-directory#
        print(f"Creating {zip}.")

        shutil.make_archive(str(zip), 'zip', self.project_dir, PackagePlugin.main_package_name)


if __name__ == '__main__':
    pp = PackagePlugin(project_cfg)
    pp.update_bl_info_version()
    pp.clean_temp_files()
    current = RhubarbBinary.currently_deployed_platform(rhubarb_cfg)  # Keep the current platform bin
    for b in RhubarbBinary.all_platforms(rhubarb_cfg):
        b.deploy_to_bin()  # Deploy the corret platfrom before zipping
        pp.zip_dist(b.platform_name)
    if current:  # Recover the previously deployed platform, if any
        current.deploy_to_bin()
