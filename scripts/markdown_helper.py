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
from markdown_it.renderer import RendererHTML

from pathlib import Path


@dataclass(frozen=True)
class MarkdownDoc:
    md_path: Path

    @cached_property
    def md_text(self) -> str:
        return self.md_path.read_text(encoding="utf8")

    @cached_property
    def md_parser(self) -> MarkdownIt:
        p = MarkdownIt("commonmark")
        p.enable("table")
        p.enable("strikethrough")  # ~~text~~
        p.enable("replacements")  # (c) (tm) (r) --> © ™ ®
        p.enable("smartquotes")
        return p

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

    def to_html(self) -> str:
        options = self.md_parser.options
        env: dict = {}
        return self.md_parser.renderer.render(self.tokens, options, env)

    def save_to(self, p: Path) -> None:
        markdown_content = self.to_html()
        p.write_text(markdown_content, encoding="utf8")


if __name__ == '__main__':
    md = MarkdownDoc(Path("README.md"))
    md.debug_print()
    md.save_to(Path("sphinx/README.html"))
