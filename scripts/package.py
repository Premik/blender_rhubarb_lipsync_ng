import re
from functools import cached_property
from pathlib import Path

from config import project_cfg


class PackagePlugin:
    """Package (zip) project for the distribution"""

    bl_info_version_pattern = r'''['"]version["']\s*:\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)'''
    bl_info_version_rx = re.compile(f"(.*)({bl_info_version_pattern})(.*)", re.DOTALL)

    def __init__(self, cfg: dict):
        assert cfg and cfg["project"]
        self.cfg = cfg

    @property
    def version_str(self) -> str:
        return self.cfg["project"]["version"]

    @cached_property
    def version_tuple(self) -> tuple[int, int, int]:
        return tuple([int(p) for p in self.version_str.split(".")])  # type: ignore

    @cached_property
    def project_dir(self) -> Path:
        return Path(__file__).parents[1]

    @cached_property
    def main__init__(self) -> Path:
        return self.project_dir / "rhubarb_lipsync" / "__init__.py"

    def update_bl_info_version(self):
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


if __name__ == '__main__':
    pp = PackagePlugin(project_cfg)
    pp.update_bl_info_version()
    # TODO Create zip archives
