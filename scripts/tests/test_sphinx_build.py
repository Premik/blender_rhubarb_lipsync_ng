import shutil
from pathlib import Path

import pytest

from dist_artifacts import DistArtifacts
from sphinx_build import SphinxBuilder


@pytest.fixture
def builder(tmp_path: Path) -> SphinxBuilder:
    builder = SphinxBuilder()
    builder.__dict__["project_dir"] = tmp_path
    builder.__dict__["dist_artifacts"] = DistArtifacts(project_dir=tmp_path, version="1.2.3")
    builder.__dict__["build_dir"] = tmp_path / "build"
    builder.__dict__["html_dir"] = tmp_path / "html"
    builder.__dict__["pdf_out_dir"] = tmp_path / "pdf"
    return builder


def test_doc_zip_base_path(builder: SphinxBuilder) -> None:
    assert builder.doc_zip_base_path() == builder.dist_dir / "rhubarb-lipsync-docs-1.2"


def test_check_dist_rejects_stale_docs_zip(builder: SphinxBuilder) -> None:
    builder.dist_artifacts.ensure_dist_dir()
    (builder.dist_dir / "rhubarb-lipsync-docs-1.1.zip").touch()

    with pytest.raises(RuntimeError, match="Unexpected"):
        builder.check_dist()


def test_check_dist_accepts_addon_zips(builder: SphinxBuilder) -> None:
    builder.dist_artifacts.ensure_dist_dir()
    (builder.dist_dir / "rhubarb_lipsync_ng-Linux-1.2.3.zip").touch()

    builder.check_dist()


def test_zip_docs_rejects_missing_archive(monkeypatch: pytest.MonkeyPatch, builder: SphinxBuilder) -> None:
    builder.build_dir.mkdir()
    builder.html_dir.mkdir()
    builder.pdf_out_dir.mkdir()
    monkeypatch.setattr(shutil, "make_archive", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="Missing"):
        builder.zip_docs()
