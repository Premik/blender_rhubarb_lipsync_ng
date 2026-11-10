import sys
from pathlib import Path

import pytest

from dist_artifacts import DistArtifacts

CFG = {"platforms": [{"name": "Linux"}, {"name": "macOS"}, {"name": "Windows"}]}
VERSION = "1.2.3"


@pytest.fixture
def artifacts(tmp_path) -> DistArtifacts:
    return DistArtifacts(project_dir=tmp_path, version=VERSION, cfg=CFG)


def touch_all(artifacts: DistArtifacts, names: list[str]) -> None:
    artifacts.ensure_dist_dir()
    for name in names:
        (artifacts.dist_dir / name).touch()


def test_release_zips(artifacts: DistArtifacts) -> None:
    assert artifacts.addon_zips == [
        "rhubarb_lipsync_ng-Linux-1.2.3.zip",
        "rhubarb_lipsync_ng-macOS-1.2.3.zip",
        "rhubarb_lipsync_ng-Windows-1.2.3.zip",
    ]
    assert artifacts.docs_zip == "rhubarb-lipsync-docs-1.2.zip"
    assert artifacts.release_zips == [*artifacts.addon_zips, artifacts.docs_zip]


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation may require privileges on Windows")
def test_ensure_dist_dir_creates_dangling_symlink_target(artifacts: DistArtifacts, tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    (tmp_path / "dist").symlink_to(target, target_is_directory=True)

    assert artifacts.ensure_dist_dir() == tmp_path / "dist"
    assert target.is_dir()


def test_check_stale_addon_zips_accepts_empty_dist(artifacts: DistArtifacts) -> None:
    artifacts.check_stale_addon_zips()

    assert artifacts.dist_dir.is_dir()


def test_check_stale_addon_zips_accepts_partial_release_set(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, artifacts.addon_zips[:1])

    artifacts.check_stale_addon_zips()


def test_check_stale_addon_zips_ignores_docs_zip(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, [artifacts.docs_zip])

    artifacts.check_stale_addon_zips()


def test_check_stale_addon_zips_rejects_stale_version(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, ["rhubarb_lipsync_ng-Linux-1.1.0.zip"])

    with pytest.raises(RuntimeError, match="Unexpected"):
        artifacts.check_stale_addon_zips()


def test_check_stale_addon_zips_rejects_unknown_platform(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, ["rhubarb_lipsync_ng-BeOS-1.2.3.zip"])

    with pytest.raises(RuntimeError, match="Unexpected"):
        artifacts.check_stale_addon_zips()


def test_check_stale_docs_zips_rejects_stale_major_minor(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, ["rhubarb-lipsync-docs-1.1.zip"])

    with pytest.raises(RuntimeError, match="Unexpected"):
        artifacts.check_stale_docs_zips()


def test_check_stale_docs_zips_ignores_addon_zips(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, [*artifacts.addon_zips, artifacts.docs_zip])

    artifacts.check_stale_docs_zips()


def test_check_missing_zips_rejects_missing_zip(artifacts: DistArtifacts) -> None:
    with pytest.raises(RuntimeError, match="Missing"):
        artifacts.check_missing_zips(["rhubarb_lipsync_ng-Linux-1.2.3.zip"])


def test_check_release_zips_accepts_full_set(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, artifacts.release_zips)

    artifacts.check_release_zips()


def test_check_release_zips_rejects_missing_docs_zip(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, artifacts.addon_zips)

    with pytest.raises(RuntimeError, match="Missing"):
        artifacts.check_release_zips()


def test_check_release_zips_rejects_missing_addon_zip(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, artifacts.release_zips[1:])

    with pytest.raises(RuntimeError, match="Missing"):
        artifacts.check_release_zips()


def test_check_release_zips_rejects_empty_dist(artifacts: DistArtifacts) -> None:
    artifacts.ensure_dist_dir()

    with pytest.raises(RuntimeError, match="Missing"):
        artifacts.check_release_zips()


def test_check_release_zips_rejects_stale_docs_zip(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, [*artifacts.addon_zips, "rhubarb-lipsync-docs-1.1.zip"])

    with pytest.raises(RuntimeError, match="Unexpected"):
        artifacts.check_release_zips()


def test_check_release_zips_rejects_unrelated_zip(artifacts: DistArtifacts) -> None:
    touch_all(artifacts, [*artifacts.release_zips, "unrelated.zip"])

    with pytest.raises(RuntimeError, match="Unexpected"):
        artifacts.check_release_zips()
