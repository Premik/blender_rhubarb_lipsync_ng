from collections.abc import Callable
from pathlib import Path

import pytest

from package import PackagePlugin


class FakeBinary:
    def __init__(self, platform_name: str, deployed: bool = True, manifest: list[str] | None = None) -> None:
        self.platform_name = platform_name
        self.bin_dir = Path("/nonexistent/bin")
        self.manifest_path = Path("/nonexistent/blender_manifest.toml")
        self.platform_blender_names = [platform_name.lower()]
        self.deployed = deployed
        self.deploy_count = 0
        self.manifest = manifest if manifest is not None else self.platform_blender_names

    def deploy_to_bin(self) -> None:
        self.deploy_count += 1

    def is_deployed_to_bin(self) -> bool:
        return self.deployed

    def manifest_platforms(self) -> list[str]:
        return self.manifest


@pytest.fixture
def plugin(tmp_path) -> PackagePlugin:
    pp = PackagePlugin({"project": {"version": "1.2.3"}})
    pp.__dict__["project_dir"] = tmp_path
    return pp


def fake_zip(plugin: PackagePlugin) -> Callable[[FakeBinary], None]:
    def zip_dist(b: FakeBinary) -> None:
        (plugin.dist_dir / f"rhubarb_lipsync_ng-{b.platform_name}-{plugin.version_str}.zip").touch()

    return zip_dist


def patch_build_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    plugin: PackagePlugin,
    selected: list[FakeBinary],
    restore: FakeBinary,
) -> list[FakeBinary]:
    prepared: list[FakeBinary] = []
    monkeypatch.setattr(plugin, "selected_platforms", lambda name: selected)
    monkeypatch.setattr(plugin, "restore_candidate", lambda: restore)
    monkeypatch.setattr(plugin, "update_version_files", lambda: None)
    monkeypatch.setattr(plugin, "clean_temp_files", lambda: None)
    monkeypatch.setattr(plugin, "ensure_binaries", prepared.extend)
    return prepared


def test_deployed_platform_restores_after_success(plugin: PackagePlugin) -> None:
    binary = FakeBinary("Windows")
    restore = FakeBinary("Linux")

    with plugin.deployed_platform(binary, restore):
        assert binary.deploy_count == 1
        assert restore.deploy_count == 0

    assert restore.deploy_count == 1


def test_deployed_platform_restores_after_error(plugin: PackagePlugin) -> None:
    binary = FakeBinary("Windows")
    restore = FakeBinary("Linux")

    with pytest.raises(RuntimeError, match="boom"):
        with plugin.deployed_platform(binary, restore):
            raise RuntimeError("boom")

    assert binary.deploy_count == 1
    assert restore.deploy_count == 1


def test_deployed_platform_without_restore_candidate(plugin: PackagePlugin) -> None:
    binary = FakeBinary("Windows")

    with plugin.deployed_platform(binary, None):
        pass

    assert binary.deploy_count == 1


def test_zip_dist_rejects_undeployed_binary(plugin: PackagePlugin) -> None:
    with pytest.raises(RuntimeError, match="not deployed"):
        plugin.zip_dist(FakeBinary("Windows", deployed=False))


def test_zip_dist_rejects_stale_manifest(plugin: PackagePlugin) -> None:
    with pytest.raises(RuntimeError, match="lists platforms"):
        plugin.zip_dist(FakeBinary("Windows", manifest=["linux-x64"]))


def test_selected_platforms_rejects_unknown_name(plugin: PackagePlugin) -> None:
    with pytest.raises(ValueError, match="No platform matches"):
        plugin.selected_platforms("nonsense")


def test_clean_dist_accepts_empty_dist(plugin: PackagePlugin) -> None:
    plugin.clean_dist()

    assert plugin.dist_dir.is_dir()


def test_clean_dist_accepts_partial_release_set(plugin: PackagePlugin) -> None:
    plugin.dist_dir.mkdir()
    (plugin.dist_dir / "rhubarb_lipsync_ng-Linux-1.2.3.zip").touch()

    plugin.clean_dist()


def test_clean_dist_rejects_stale_addon_zip(plugin: PackagePlugin) -> None:
    plugin.dist_dir.mkdir()
    (plugin.dist_dir / "rhubarb_lipsync_ng-Linux-1.1.0.zip").touch()

    with pytest.raises(RuntimeError, match="Unexpected"):
        plugin.clean_dist()


def test_build_prepares_restore_candidate_outside_selection(monkeypatch: pytest.MonkeyPatch, plugin: PackagePlugin) -> None:
    windows = FakeBinary("Windows")
    linux = FakeBinary("Linux")
    prepared = patch_build_side_effects(monkeypatch, plugin, [windows], linux)
    monkeypatch.setattr(plugin, "zip_dist", fake_zip(plugin))

    plugin.build("Windows")

    assert [b.platform_name for b in prepared] == ["Windows", "Linux"]
    assert windows.deploy_count == 1
    assert linux.deploy_count == 1


def test_build_restores_restore_candidate_after_failure(monkeypatch: pytest.MonkeyPatch, plugin: PackagePlugin) -> None:
    windows = FakeBinary("Windows")
    linux = FakeBinary("Linux")
    patch_build_side_effects(monkeypatch, plugin, [windows], linux)

    def fail_zip(b: FakeBinary) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin, "zip_dist", fail_zip)

    with pytest.raises(RuntimeError, match="boom"):
        plugin.build("Windows")

    assert linux.deploy_count == 1


def test_build_rejects_missing_built_zip(monkeypatch: pytest.MonkeyPatch, plugin: PackagePlugin) -> None:
    windows = FakeBinary("Windows")
    patch_build_side_effects(monkeypatch, plugin, [windows], windows)
    monkeypatch.setattr(plugin, "zip_dist", lambda b: None)

    with pytest.raises(RuntimeError, match="Missing"):
        plugin.build("Windows")
