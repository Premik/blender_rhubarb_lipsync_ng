"""Expected dist/ artifacts for a release and helpers to validate them."""

from collections.abc import Collection
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import ClassVar

from config import dist_zip_name, project_cfg, rhubarb_cfg


@dataclass(frozen=True)
class DistArtifacts:
    """Expected dist/ artifacts for a release and helpers to validate them."""

    addon_zip_glob: ClassVar[str] = "rhubarb_lipsync_ng-*.zip"
    docs_zip_glob: ClassVar[str] = "rhubarb-lipsync-docs-*.zip"

    project_dir: Path = field(default_factory=lambda: Path(__file__).parents[1])
    version: str = field(default_factory=lambda: project_cfg["project"]["version"])
    cfg: dict = field(default_factory=lambda: rhubarb_cfg)

    @cached_property
    def dist_dir(self) -> Path:
        return self.project_dir / "dist"

    def ensure_dist_dir(self) -> Path:
        """Create the dist target dir (dist may be a dangling symlink) and return it."""
        self.dist_dir.resolve().mkdir(parents=True, exist_ok=True)
        return self.dist_dir

    @property
    def docs_zip_stem(self) -> str:
        major, minor = self.version.split(".")[:2]
        return f"rhubarb-lipsync-docs-{major}.{minor}"

    @property
    def docs_zip(self) -> str:
        return f"{self.docs_zip_stem}.zip"

    @property
    def addon_zips(self) -> list[str]:
        return [f"{dist_zip_name(p['name'], self.version)}.zip" for p in self.cfg["platforms"]]

    @property
    def release_zips(self) -> list[str]:
        """All zips a complete release consists of."""
        return [*self.addon_zips, self.docs_zip]

    def check_stale_zips(self, expected: Collection[str], pattern: str = "*.zip") -> None:
        """Fail if dist/ contains zips matching `pattern` that are not expected (e.g. another version)."""
        actual = {p.name for p in self.dist_dir.glob(pattern)}
        unexpected = sorted(actual - set(expected))
        if unexpected:
            raise RuntimeError(f"Unexpected dist zip(s) in {self.dist_dir}: {unexpected}. Remove or move them away.")

    def check_missing_zips(self, expected: Collection[str]) -> None:
        missing = sorted(name for name in expected if not (self.dist_dir / name).is_file())
        if missing:
            raise RuntimeError(f"Missing dist zip(s) in {self.dist_dir}: {missing}.")

    def check_stale_addon_zips(self) -> None:
        self.ensure_dist_dir()
        self.check_stale_zips(self.addon_zips, self.addon_zip_glob)

    def check_stale_docs_zips(self) -> None:
        self.ensure_dist_dir()
        self.check_stale_zips([self.docs_zip], self.docs_zip_glob)

    def check_release_zips(self) -> None:
        """Fail unless dist/ contains exactly the full release artifact set."""
        self.ensure_dist_dir()
        self.check_stale_zips(self.release_zips)
        self.check_missing_zips(self.release_zips)


if __name__ == '__main__':
    artifacts = DistArtifacts()
    artifacts.check_release_zips()
    print(f"dist/ contains exactly the expected release zips for {artifacts.version}")
