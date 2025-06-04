import shutil
import subprocess
import sys
from functools import cached_property
from pathlib import Path

from config import project_cfg
from dataclasses import dataclass
from typing import Any, List  # Make sure 'Any' is kept if used elsewhere, otherwise it can be removed.


from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdown_it.utils import OptionsDict

from pathlib import Path


@dataclass(frozen=True)
class MarkdownDoc:
    md_path: Path

    @cached_property
    def md_text(self) -> str:
        return self.md_path.read_text(encoding="utf8")

    @cached_property
    def md_parser(self) -> MarkdownIt:
        return MarkdownIt()

    @cached_property
    def tokens(self) -> List[Token]:  # Updated type hint from List[Any]
        return self.md_parser.parse(self.md_text)

    def debug_print(self) -> None:
        for idx, token in enumerate(self.tokens):
            content_preview = ""
            if token.content:
                content_preview = token.content[:50].replace("\n", "\\n")
            print(
                f"{idx}: type={getattr(token, 'type', None)} "
                f"tag={getattr(token, 'tag', None)} "
                f"nesting={getattr(token, 'nesting', None)} "
                f"content='{content_preview}...'"
            )

    def to_markdown(self) -> str:
        options = self.md_parser.options
        env: dict = {}
        return self.md_parser.renderer.render(self.tokens, options, env)

    def save_to(self, p: Path) -> None:
        markdown_content = self.to_markdown()
        p.write_text(markdown_content, encoding="utf8")


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
        process = None
        try:
            process = subprocess.run(
                ["sphinx-build", "-b", "html", str(self.sphinx_dir), str(self.html_dir)],
                capture_output=True,
                text=True,
                check=True,
            )
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
        finally:
            if process:
                print(process.stdout)
                if process.stderr:
                    print(process.stderr)


if __name__ == '__main__':
    builder = SphinxBuilder(project_cfg)
    # builder.build_docs()
    md = MarkdownDoc(Path("README.md"))
    md.debug_print()
    md.save_to(Path("sphinx/README.md"))
