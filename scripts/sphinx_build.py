import shutil
import subprocess
import sys
from functools import cached_property
from pathlib import Path

from config import project_cfg


class SphinxBuilder:
    """Builds the Sphinx documentation."""

    def __init__(self, cfg: dict) -> None:
        assert cfg and cfg["project"]
        self.cfg = cfg

    @cached_property
    def project_dir(self) -> Path:
        return Path(__file__).parents[1]

    @cached_property
    def sphinx_dir(self) -> Path:
        return self.project_dir / "sphinx"

    @cached_property
    def build_dir(self) -> Path:
        return self.sphinx_dir / "build"

    @cached_property
    def html_dir(self) -> Path:
        return self.build_dir / "html"

    def clean_build(self) -> None:
        """Removes the existing build directory."""
        if self.build_dir.exists():
            print(f"Removing existing build directory: {self.build_dir}")
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(parents=True, exist_ok=True)

    def build_docs(self) -> None:
        """Builds the Sphinx documentation."""
        self.clean_build()
        print(f"Building Sphinx documentation in {self.sphinx_dir}")
        try:
            process = subprocess.run(
                ["sphinx-build", "-b", "html", str(self.sphinx_dir), str(self.html_dir)],
                capture_output=True,
                text=True,
                check=True,
            )
            print(process.stdout)
            if process.stderr:
                print("Sphinx Warnings/Errors:")
                print(process.stderr)
            print(f"Sphinx documentation built successfully in {self.html_dir}")
        except subprocess.CalledProcessError as e:
            print(f"Error building Sphinx documentation: {e}")
            print(e.stdout)
            if e.stderr:
                print("Sphinx Stderr:")
                print(e.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print("Error: sphinx-build command not found. Make sure Sphinx is installed and in your PATH.")
            sys.exit(1)


if __name__ == '__main__':
    builder = SphinxBuilder(project_cfg)
    builder.build_docs()
