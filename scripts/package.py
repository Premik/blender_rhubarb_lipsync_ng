import re
import shutil
import sys
from functools import cached_property
from pathlib import Path

from config import dist_zip_name, project_cfg, rhubarb_cfg
from rhubarb_bin import RhubarbBinary


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
    bl_info_version_rx = re.compile(bl_info_version_pattern)

    misc_ops_pattern = r'''return\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)'''
    misc_ops_version_rx = re.compile(misc_ops_pattern)

    readme_version_zip_pattern = r'-\d+\.\d+\.\d+\.zip'
    readme_version_zip_rx = re.compile(readme_version_zip_pattern)

    readme_version_release_url_pattern = r'/v\d+\.\d+\.\d+/'
    readme_version_release_url_rx = re.compile(readme_version_release_url_pattern)

    blender_manifest_pattern = r'^\s*version\s*=\s*["]\d+\.\d+\.\d+["]'
    blender_manifest_rx = re.compile(blender_manifest_pattern)

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
    def main__init_path(self) -> Path:
        return self.project_dir / PackagePlugin.main_package_name / "__init__.py"

    @cached_property
    def misc_ops_path(self) -> Path:
        return self.project_dir / PackagePlugin.main_package_name / "blender" / "misc_operators.py"

    @cached_property
    def readme_md_path(self) -> Path:
        return self.project_dir / "README.md"

    @cached_property
    def blender_manifest_path(self) -> Path:
        return self.project_dir / PackagePlugin.main_package_name / "blender_manifest.toml"

    @cached_property
    def dist_dir(self) -> Path:
        return self.project_dir / "dist"

    def update_version_in_file(self, rx: re.Pattern[str], p: Path, new_ver: str) -> None:
        assert p.exists(), f"The {p} doesn't exist"

        replacement_count = 0
        updated_lines = []

        def replace_match(m) -> str:
            return new_ver

        with open(p, 'r', encoding='utf-8') as s:
            for line in s:
                new_line = rx.sub(replace_match, line)  # Replaces all occurrences
                num_replacements = len(re.findall(rx, line))  # Count how many replacements were made
                replacement_count += num_replacements
                updated_lines.append(new_line)

        assert replacement_count > 0, f"Failed to update any lines in the {p}. Pattern\n{rx}"

        with open(p, 'w', encoding='utf-8') as s:
            s.writelines(updated_lines)

        print(f"Updated {replacement_count} version string(s) to '{new_ver}' in the {p}")

    def update_version_files(self) -> None:
        self.update_version_in_file(PackagePlugin.bl_info_version_rx, self.main__init_path, f"'version': {self.version_tuple}")
        self.update_version_in_file(PackagePlugin.misc_ops_version_rx, self.misc_ops_path, f'return {self.version_tuple}')
        self.update_version_in_file(PackagePlugin.readme_version_zip_rx, self.readme_md_path, f"-{self.version_str}.zip")
        self.update_version_in_file(PackagePlugin.readme_version_release_url_rx, self.readme_md_path, f"/v{self.version_str}/")
        self.update_version_in_file(PackagePlugin.blender_manifest_rx, self.blender_manifest_path, f'version = "{self.version_str}"')

    def clean_temp_files(self) -> None:
        d = clean_temp_files_at(self.project_dir)
        print(f"Deleted {d} temp/cache files/dirs from the {self.project_dir}")

    def dist_zip_path(self, platform: str) -> Path:
        return self.dist_dir / dist_zip_name(platform, self.version_str)

    def github_release_url(self, platform: str) -> str:
        zip = self.dist_zip_path(platform).name
        #  https://github.com/Premik/blender_rhubarb_lipsync_ng/releases/download/v1.5.0/rhubarb_lipsync_ng-Windows-1.5.0

        return f"https://github.com/Premik/blender_rhubarb_lipsync_ng/releases/download/v{self.version_str}/{zip}"

    def zip_dist(self, platform: str) -> None:
        """Creates the zip for distribution. Assumes the correct binaries are already deployed in the bin_dir subfolder"""
        zip = self.dist_zip_path(platform)
        # https://stackoverflow.com/questions/1855095/how-to-create-a-zip-archive-of-a-directory#
        print(f"Creating {zip}.")
        shutil.make_archive(str(zip), 'zip', self.project_dir, PackagePlugin.main_package_name)


if __name__ == '__main__':
    platform_name = sys.argv[1] if len(sys.argv) > 1 else ""
    pp = PackagePlugin(project_cfg)
    pp.update_version_files()

    pp.clean_temp_files()
    current = RhubarbBinary.currently_deployed_platform(rhubarb_cfg)  # Keep the current platform bin
    for b in RhubarbBinary.platforms_by_name(platform_name, rhubarb_cfg):
        if not b.is_deployed_to_bin():
            b.deploy_to_bin()  # Deploy the correct platform before zipping
        pp.zip_dist(b.platform_name)

    if current:  # Recover the previously deployed platform, if any
        current.deploy_to_bin()
