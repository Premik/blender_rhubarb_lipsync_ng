import platform
import re
import shutil
import sys
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import Iterator, Optional

from config import dist_zip_name, project_cfg, rhubarb_cfg
from dist_artifacts import DistArtifacts
from rhubarb_bin import RhubarbBinary


def clean_temp_files_at(start_path: Path) -> int:
    # https://stackoverflow.com/questions/28991015/python3-project-remove-pycache-folders-and-pyc-files
    deleted = 0
    for p in start_path.rglob('*.py[cod]'):
        p.unlink()
        deleted += 1
    for p in start_path.rglob('__pycache__'):
        shutil.rmtree(p, ignore_errors=True)
        deleted += 1
    for p in start_path.rglob('.mypy_cache'):
        shutil.rmtree(p, ignore_errors=True)
        deleted += 1
    for p in start_path.rglob('.ruff_cache'):
        shutil.rmtree(p, ignore_errors=True)
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

    sphinx_conf_pattern = r"^\s*release\s*=\s*[']\d+\.\d+[']"
    sphinx_conf_rx = re.compile(sphinx_conf_pattern)

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
    def sphinx_conf_path(self) -> Path:
        return self.project_dir / "sphinx" / "conf.py"

    @cached_property
    def dist_artifacts(self) -> DistArtifacts:
        return DistArtifacts(project_dir=self.project_dir, version=self.version_str, cfg=rhubarb_cfg)

    @cached_property
    def dist_dir(self) -> Path:
        return self.dist_artifacts.dist_dir

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
        self.update_version_in_file(PackagePlugin.sphinx_conf_rx, self.sphinx_conf_path, f"release = '{self.version_tuple[0]}.{self.version_tuple[1]}'")

    def clean_temp_files(self) -> None:
        d = clean_temp_files_at(self.project_dir)
        print(f"Deleted {d} temp/cache files/dirs from the {self.project_dir}")

    def dist_zip_base_path(self, platform: str) -> Path:
        """Zip path without the .zip suffix (shutil.make_archive appends it)."""
        return self.dist_dir / dist_zip_name(platform, self.version_str)

    def dist_zip_path(self, platform: str) -> Path:
        base = self.dist_zip_base_path(platform)
        return base.with_name(base.name + ".zip")

    def github_release_url(self, platform: str) -> str:
        zip = self.dist_zip_path(platform).name
        #  https://github.com/Premik/blender_rhubarb_lipsync_ng/releases/download/v1.5.0/rhubarb_lipsync_ng-Windows-1.5.0

        return f"https://github.com/Premik/blender_rhubarb_lipsync_ng/releases/download/v{self.version_str}/{zip}"

    def clean_dist(self) -> None:
        """Fail if dist/ contains addon zips that are not part of this release."""
        self.dist_artifacts.check_stale_addon_zips()

    def zip_dist(self, b: RhubarbBinary) -> None:
        """Creates the zip for distribution, ensuring the deployed binary and manifest match the platform being packaged."""
        if not b.is_deployed_to_bin():
            raise RuntimeError(f"The {b.platform_name} binary is not deployed to {b.bin_dir}. Run scripts/rhubarb_bin.py first.")
        manifest_platforms = b.manifest_platforms()
        if manifest_platforms != b.platform_blender_names:
            raise RuntimeError(
                f"The manifest {b.manifest_path} lists platforms {manifest_platforms}, "
                f"expected {b.platform_blender_names} for {b.platform_name}. Run scripts/rhubarb_bin.py first."
            )
        zip = self.dist_zip_path(b.platform_name)
        # https://stackoverflow.com/questions/1855095/how-to-create-a-zip-archive-of-a-directory#
        print(f"Creating {zip}.")
        shutil.make_archive(str(self.dist_zip_base_path(b.platform_name)), 'zip', self.project_dir, PackagePlugin.main_package_name)

    def selected_platforms(self, name: str) -> list[RhubarbBinary]:
        platforms = RhubarbBinary.platforms_by_name(name, rhubarb_cfg)
        if platforms:
            return platforms
        available = [b.platform_name for b in RhubarbBinary.all_platforms(rhubarb_cfg)]
        raise ValueError(f"No platform matches '{name}'. Available platforms: {available}")

    def restore_candidate(self) -> Optional[RhubarbBinary]:
        """Platform to redeploy after packaging: the currently deployed one, else the host's."""
        current = RhubarbBinary.currently_deployed_platform(rhubarb_cfg)
        if current is not None:
            return current
        return next((b for b in RhubarbBinary.all_platforms(rhubarb_cfg) if b.matches_platform(platform.system())), None)

    def ensure_binaries(self, binaries: list[RhubarbBinary]) -> None:
        for b in {b.platform_name: b for b in binaries}.values():
            b.ensure_download()
            b.verify_download_checksum()
            b.ensure_unzipped()

    @contextmanager
    def deployed_platform(self, b: RhubarbBinary, restore: Optional[RhubarbBinary]) -> Iterator[None]:
        """Deploy b for the block, restoring `restore` afterwards.

        Always deploys, so the binary and manifest cannot be stale for the platform being zipped.
        """
        try:
            b.deploy_to_bin()
            yield
        finally:
            if restore is not None:
                restore.deploy_to_bin()

    def build(self, platform_name: str = "") -> None:
        """Package the plugin for the selected platforms (all when no name is given)."""
        platforms = self.selected_platforms(platform_name)
        self.clean_dist()
        self.update_version_files()
        self.clean_temp_files()

        restore = self.restore_candidate()
        to_prepare = list(platforms)
        if restore is not None:
            to_prepare.append(restore)
        self.ensure_binaries(to_prepare)

        for b in platforms:
            with self.deployed_platform(b, restore):
                self.zip_dist(b)
        self.dist_artifacts.check_missing_zips([self.dist_zip_path(b.platform_name).name for b in platforms])


if __name__ == '__main__':
    platform_name = sys.argv[1] if len(sys.argv) > 1 else ""
    PackagePlugin(project_cfg).build(platform_name)
