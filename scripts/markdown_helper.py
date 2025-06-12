import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import List, Optional

from markdown_it import MarkdownIt
from PIL import Image
from markdown_it.token import Token


@dataclass(frozen=True)
class MarkdownDoc:
    md_path: Path

    @cached_property
    def md_text(self) -> str:
        return self.md_path.read_text(encoding="utf8")

    @cached_property
    def md_lines(self) -> List[str]:
        return self.md_text.splitlines()

    @cached_property
    def md_parser(self) -> MarkdownIt:
        p = MarkdownIt("commonmark")
        p.enable("table")
        p.enable("strikethrough")  # ~~text~~
        p.enable("replacements")  # (c) (tm) (r) --> © ™ ®
        p.enable("smartquotes")
        return p

    @cached_property
    def tokens(self) -> List[Token]:
        return self.md_parser.parse(self.md_text)

    def find_matching_close_token(self, open_token: Token, tokens: Optional[List[Token]] = None) -> Optional[Token]:
        """
        For an '_open' token, find the corresponding '_close' token by type and same nesting level.
        """
        if tokens is None:
            tokens = self.tokens
        open_type = open_token.type
        if not open_type.endswith('_open'):
            raise ValueError(f"Token type does not end with '_open': {open_type}")

        close_type = open_type[:-5] + '_close'
        start_idx = tokens.index(open_token)
        last_map = None
        for token in tokens[start_idx + 1 :]:
            if token.map:
                last_map = token.map
            if token.type == close_type and token.level == open_token.level:
                if not token.map and last_map:  # Closing Tokens for some reason are missing line info, use from previous line
                    token.map = [last_map[1] - 1, last_map[1]]
                return token
        return None

    @cached_property
    def parent_by_token_id(self) -> dict[int, Optional[Token]]:
        """
        Maps token id (id(token)) to its parent Token (or None for root tokens).
        """
        parent_map: dict[int, Optional[Token]] = {}

        def walk_tokens(tokens: List[Token], parent_token: Optional[Token] = None) -> None:
            for token in tokens:
                parent_map[id(token)] = parent_token
                if token.children:
                    walk_tokens(token.children, token)

        walk_tokens(self.tokens)
        return parent_map

    @cached_property
    def block_by_token_id(self) -> dict[int, List[Token]]:
        """
        Maps token id (id(token)) to the stack of currently open block tokens
        (outermost first, innermost last) that 'own' this token.
        """
        block_map: dict[int, List[Token]] = {}
        stack: List[Token] = []

        def walk_tokens(tokens: List[Token]) -> None:
            for token in tokens:
                # Store the current stack as this token's block ancestry
                block_map[id(token)] = stack.copy()

                # Manage block opening/closing
                if token.block and token.nesting == 1:
                    stack.append(token)
                if token.children:
                    walk_tokens(token.children)
                if token.block and token.nesting == -1:
                    if stack and stack[-1].type == token.type:
                        stack.pop()

        walk_tokens(self.tokens)
        return block_map

    @cached_property
    def child_block_by_token_id(self) -> dict[int, List[Token]]:
        """
        Maps block token id to the list of tokens that are direct (one level deep) children of that block.
        Only direct children are included, not nested descendants.
        """
        child_blocks: dict[int, List[Token]] = {}

        for token in self.tokens:
            stack = self.block_by_token_id.get(id(token), [])
            if stack:
                parent_block = stack[-1]
                child_blocks.setdefault(id(parent_block), []).append(token)

        return child_blocks

    @cached_property
    def tokens_by_type(self) -> dict[str, List[Token]]:
        type_map: dict[str, List[Token]] = {}

        def walk(tokens: List[Token]) -> None:
            for t in tokens:
                type_map.setdefault(t.type, []).append(t)
                if t.children:
                    walk(t.children)

        walk(self.tokens)
        return type_map

    def get_parents(self, token: Token) -> List[Token]:
        """
        Returns the list of parent tokens (from immediate parent up the ancestry).
        """
        parents: List[Token] = []
        curr = self.parent_by_token_id.get(id(token))
        for _ in range(100):
            if curr is None:
                return parents
            parents.append(curr)
            curr = self.parent_by_token_id.get(id(curr))
        raise RuntimeError("Cyclic graph")

    def get_parent_blocks(self, token: Token) -> List[Token]:
        """
        Returns the list of parent tokens (from furthest ancestor to immediate parent),
        then the list of blocks (outermost to innermost) that own this token.
        Each token appears only once.
        """
        # Gather ancestors: furthest (root) to immediate parent
        parents: List[Token] = self.get_parents(token) + [token]
        topmost_p = parents[0]
        blocks = self.block_by_token_id.get(id(topmost_p), [])
        return blocks + parents

    def find_token_lines(self, token: Token) -> Optional[range]:
        if not token:
            return None
        parent_tokens = self.get_parents(token)
        pts = [t.map for t in reversed(parent_tokens) if t.map]
        if not pts:
            return None
        return range(pts[0][0], pts[0][1])

    def find_children(self, content_rx: str, type: str, tokens: List[Token]) -> List[Token]:
        pattern = re.compile(content_rx)
        matches: List[Token] = []
        if not tokens:
            return []

        def walk_tokens(tokens: List[Token]) -> None:
            if not tokens:
                return
            for token in tokens:
                walk_tokens(token.children)
                walk_tokens(self.child_block_by_token_id.get(id(token), None))
                if type and token.type != type:
                    continue
                if token.children:
                    continue  # Don't match parent content since it is composet of children anyway
                if pattern.search(token.content):
                    matches.append(token)

        for root_t in tokens:
            ch = root_t.children if root_t.children else []
            walk_tokens(ch + [root_t])
        return matches

    @cached_property
    def root_tokens_by_line(self) -> dict[int, Token]:
        """
        Maps line number (0-based) to the root-level token that starts on that line.
        Only includes tokens that have map information and are at nesting level 0.
        """
        line_map: dict[int, Token] = {}
        for token in self.tokens:
            if token.map and token.level == 0:
                start_line = token.map[0]
                line_map[start_line] = token
        return line_map

    def find_next_token(self, start_line: int = 0, type_pattern: str = ".*") -> Optional[Token]:
        """
        Find the first token starting from start_line that matches the type pattern.

        Args:
            start_line: Line number to start searching from (0-based, inclusive)
            type_pattern: Regular expression pattern to match against token.type

        Returns:
            First matching token or None if not found
        """
        pattern = re.compile(type_pattern)

        for token in self.tokens:
            if not token.map:
                continue
            token_start_line = token.map[0]
            if token_start_line >= start_line and pattern.search(token.type):
                return token

        return None

    def find_in_child_tokens(self, token_type: str, content_rx: str, start_line=-1) -> List[Token]:
        ret = []
        seen: set[int] = set()  # Keep track of seen tokens
        for h in self.tokens_by_type[token_type]:
            if h.map and h.map[0] < start_line:
                continue
            children = self.find_children(content_rx, "", self.child_block_by_token_id[id(h)])
            for child in children:
                if id(child) not in seen:
                    ret.append(child)
                    seen.add(id(child))

        return ret

    def find_block(self, block_name: str, content_rx: str, start_line=-1) -> Optional[Token]:
        matches = self.find_in_child_tokens(f"{block_name}_open", content_rx, start_line)
        if len(matches) != 1:
            n = '\n'
            raise ValueError(f"Regex matches {len(matches)} {block_name}s, expected exactly 1. {n}{n.join([str(m) for m in matches])}")
        t = matches[0]
        parent = self.parent_by_token_id.get(id(t))
        if parent is None:
            raise ValueError(f"{block_name} token has no parent")
        blocks = self.block_by_token_id.get(id(parent), [])
        blocks.reverse()
        for b in blocks:
            if b.type.startswith(f'{block_name}_'):
                return b
        raise ValueError(f"No {block_name} block found within parent.")

    def debug_print(self) -> None:
        for idx, token in enumerate(self.tokens):
            m: List[int] = token.map
            ln = ""
            if m:
                if m[1] - m[0] < 2:
                    ln = f"{m[0] + 1:02}"
                else:
                    ln = f"{m[0] + 1:02}-{m[1]:02}"
            print(f"{ln:<8}{' '*token.level}{token}")
            if m and m[0] > 70:
                print("...")
                break

    def to_html(self) -> str:
        options = self.md_parser.options
        env: dict = {}
        return self.md_parser.renderer.render(self.tokens, options, env)

    def get_image_tokens(self) -> List[Token]:
        """Find all image tokens in the document."""
        return self.tokens_by_type.get("image", [])


@dataclass(frozen=True)
class MarkdownLineEditor:
    md_path: Path
    sanitize: bool = False

    @cached_property
    def md(self) -> MarkdownDoc:
        return MarkdownDoc(self.md_path)

    def sanitize_line(self, l: str) -> str:
        # Rinoh doesn't support the doublespace at the end to force newline
        l = re.sub(r"  $", "\n", l)
        l = l.replace("✔", "[OK]").replace("❌", "[FAILED]")
        l = l.replace("⌄", "v")

        return l

    @cached_property
    def edited_lines(self) -> List[Optional[str]]:
        # Initially, they are filled with exact lines of the md_lines.
        lines: List[str] = self.md.md_lines.copy()
        if not self.sanitize:
            return lines
        sanitized_lines: List[str] = [self.sanitize_line(line) for line in lines]
        return sanitized_lines

    def delete_lines(self, start: int, end: int) -> None:
        """Set lines in edited_lines[start:end] to None (0-based, end exclusive)"""
        edited = self.edited_lines
        for i in range(start, end):
            if 0 <= i < len(edited):
                edited[i] = None

    def edited_markdown(self) -> str:
        return "\n".join(line for line in self.edited_lines if line is not None)

    def save_to(self, p: Path) -> None:
        markdown_content = self.edited_markdown()
        p.write_text(markdown_content, encoding="utf8")

    def delete_to_next_chapter(self, from_line: int) -> None:
        next_heading = self.md.find_next_token(from_line + 1, r"heading_open")
        if next_heading:
            to_line = next_heading.map[0]
        else:
            to_line = len(self.md.md_lines)  # remove to end

        self.delete_lines(from_line, to_line)

    def delete_chapter(self, rx: str, keep_heading=False) -> None:
        self.delete_block("heading", rx, keep_heading)

    def delete_paragraph(self, rx: str, keep_heading=False) -> None:
        self.delete_block("paragraph", rx, keep_heading)

    def delete_table(self, rx: str, keep_heading=False) -> None:
        self.delete_block("table", rx, keep_heading)

    def delete_block(self, block_name: str, rx: str, keep_heading=False) -> None:
        h = self.md.find_block(block_name, rx)
        if not h:
            raise ValueError(f"No {block_name} matching {rx} found")
        from_line = h.map[0]
        if keep_heading:
            from_line += 1
        self.delete_to_next_chapter(from_line)

    def get_image_scale(self, image_path: Path, max_size: int) -> Optional[int]:
        """Calculate the scale percentage for an image to fit within a max_size."""
        if not image_path.exists():
            print(f"Warning: Image file not found at {image_path}")
            return None
        with Image.open(image_path) as img:
            width, height = img.size
            if width <= max_size and height <= max_size:
                return None
            scale_w = max_size / width if width > 0 else 1
            scale_h = max_size / height if height > 0 else 1
            scale = min(scale_w, scale_h)
            return int(scale * 100)

    def create_rst_image(self, img_path: str, scale: Optional[int] = None) -> str:
        scale_line = f"\n   :scale: {scale}%" if scale else ""
        return f"```{{eval-rst}}\n.. image:: {img_path}{scale_line}\n```"

    def replace_images_with_rst(self, max_size: int = 520) -> None:
        """Replace all markdown-style images with rst-style images, scaling them if they are too large."""
        img_tokens = self.md.get_image_tokens()
        for token in img_tokens:
            line_range = self.md.find_token_lines(token)
            assert line_range is not None
            line_index = line_range[-1]  # Take the last index or range
            img_path_str = token.attrs.get("src")
            if not img_path_str:
                continue
            # Images in md are relative to the md file.
            img_path = self.md.md_path.parent / Path(img_path_str)
            scale = self.get_image_scale(img_path, max_size)
            rst_img = self.create_rst_image(img_path_str, scale)
            # This assumes the image is on a line by itself
            self.edited_lines[line_index] = rst_img


if __name__ == '__main__':
    # md = MarkdownLineEditor(Path("test.md"))
    # md.replace_images_with_rst()
    # md.md.debug_print()
    # md.save_to(Path("test_out.md"))

    # exit(0)
    md = MarkdownLineEditor(Path("README.md"))
    md.md.debug_print()
    md.replace_images_with_rst()  # Workaround. Rinoh doesn't size some wide images properly and they'd overflow the page. But not when rst is used
    md.save_to(Path("sphinx/build/md_temp/README.md"))
    exit(0)

    # print(md.find_block("heading", ".*Rh.*"))

    md.delete_chapter("Rhubarb Lip.*Blender plugin", keep_heading=True)

    # md.delete_chapter("Video tutorials", keep_heading=False)
    # md.delete_chapter("Quick Intro", keep_heading=False)
    # md.delete_chapter("Combining Armature Actions with Shape Keys", keep_heading=False)

    md.delete_chapter("More details", keep_heading=False)
    md.delete_chapter("Contributions", keep_heading=False)
    md.delete_table("🪟 Windows")
    md.save_to(Path("sphinx/README.md"))
