import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from markdown_helper import MarkdownLineEditor
from PIL import Image


@dataclass
class SphinxBuilder:
    """Builds the Sphinx documentation."""

    sanitize: bool = False

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
    def doc_root_dir(self) -> Path:
        return self.build_dir / "md_temp"

    @cached_property
    def media_dir(self) -> Path:
        return self.doc_root_dir / "doc" / "img"

    @cached_property
    def html_dir(self) -> Path:
        return self.build_dir / "html"

    @cached_property
    def pdf_out_dir(self) -> Path:
        return self.build_dir / "pdf"

    def copy_readme(self) -> None:
        md = MarkdownLineEditor(self.project_dir / "README.md", self.sanitize)
        md.delete_chapter("Rhubarb Lip.*Blender plugin", keep_heading=True)

        # md.delete_chapter("Video tutorials", keep_heading=False)
        # md.delete_chapter("Quick Intro", keep_heading=False)
        # md.delete_chapter("Combining Armature Actions with Shape Keys", keep_heading=False)

        md.delete_chapter("More details", keep_heading=False)
        md.delete_chapter("Contributions", keep_heading=False)
        md.delete_table("🪟 Windows")
        md.save_to(self.doc_root_dir / "README.md")

    def copy_media(self) -> None:
        src = self.project_dir / "doc" / "img"
        dest = self.media_dir
        if dest.exists():
            print(f"Removing existing media directory: {dest}")
            shutil.rmtree(dest)
        print(f"Copying {src} to {dest}")
        shutil.copytree(src, dest)
        shutil.copy(self.project_dir / "support/blendermarket/assetsUp/RLSP-banner.png", dest)

    def copy_faq(self) -> None:
        src = self.project_dir / "faq.md"
        dest = self.doc_root_dir / "faq.md"
        print(f"Copying {src} to {dest}")
        shutil.copy(src, dest)

    def copy_troubleshooting(self) -> None:
        md = MarkdownLineEditor(self.project_dir / "troubleshooting.md", self.sanitize)
        md.delete_chapter("Additional detail", keep_heading=False)
        md.save_to(self.doc_root_dir / "troubleshooting.md")

    def copy_release_notes(self) -> None:
        src = self.project_dir / "release_notes.md"
        dest = self.doc_root_dir / "release_notes.md"
        print(f"Copying {src} to {dest}")
        shutil.copy(src, dest)

    def copy_docs_to_root(self) -> None:
        self.doc_root_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.sphinx_dir / "index.rst", self.doc_root_dir / "index.rst")
        shutil.copy(self.sphinx_dir / "conf.py", self.doc_root_dir / "conf.py")
        for d in ["static", "templates"]:
            src = self.sphinx_dir / d
            dest = self.doc_root_dir / d
            if dest.exists():
                shutil.rmtree(dest)
            if src.exists():
                shutil.copytree(src, dest)
        self.copy_readme()
        self.copy_media()
        self.copy_faq()
        self.copy_troubleshooting()
        self.copy_release_notes()

    def clean_build(self) -> None:
        to_clean = [self.html_dir, self.pdf_out_dir, self.doc_root_dir]
        for path in to_clean:
            if path.exists():
                print(f"Removing existing output directory: {path}")
                shutil.rmtree(path)
        self.build_dir.mkdir(parents=True, exist_ok=True)

    def sphinx_build(self, build_type: str, target_dir: Path) -> None:
        """Builds the Sphinx documentation."""
        print(f"Building Sphinx documentation in {self.doc_root_dir}")
        process = None
        try:
            process = subprocess.run(
                ["sphinx-build", "-b", build_type, str(self.doc_root_dir), str(target_dir)],
                capture_output=True,
                text=True,
                check=True,
            )
            print(f"Sphinx documentation built successfully in {target_dir}")
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

    def sphinx_build_html(self) -> None:
        self.sphinx_build("html", self.html_dir)

    def sphinx_build_pdf(self) -> None:
        self.sphinx_build("rinoh", self.pdf_out_dir)

    def unanime_gif(self, gif_path: Path) -> None:
        """Takes a path to an (animated) gif, extracts the middle frame, and saves it as a single-frame gif,
        overwriting the original file."""
        if not gif_path.exists():
            print(f"Gif file not found at {gif_path}")
            return
        with Image.open(gif_path) as im:
            if not getattr(im, "is_animated", False):
                # print(f"Image at {gif_path} is not an animated gif.")
                return
            middle_frame_index = im.n_frames // 2
            im.seek(middle_frame_index)
            print(f"Unanimating {gif_path}, saving frame {middle_frame_index+1}/{im.n_frames}")
            # A copy is needed, otherwise the save fails with "cannot write mode P as G"
            frame = im.copy()
            frame.save(gif_path)

    def unanime_gifs(self, folder: Path) -> None:
        """Takes a folder path and recursively finds all .gif files, then calls unanime_gif on each."""
        if not folder.exists() or not folder.is_dir():
            print(f"Folder not found at {folder}")
            return
        for gif_path in folder.rglob("*.gif"):
            self.unanime_gif(gif_path)

    def build_html(self) -> None:
        self.sanitize = False
        self.copy_docs_to_root()
        self.sphinx_build_html()

    def build_pdf(self) -> None:
        self.sanitize = True
        self.copy_docs_to_root()
        self.unanime_gifs(builder.media_dir)
        self.sphinx_build_pdf()


if __name__ == '__main__':
    builder = SphinxBuilder()
    builder.clean_build()
    builder.build_html()
    builder.build_pdf()
