import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from functools import cached_property
from itertools import groupby
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import project_cfg

RED = "\033[91m"
RESET = "\033[0m"

ANSI_ESCAPE_RX = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RX.sub("", text)


def to_wine_path(path: Path) -> str:
    return subprocess.check_output(['winepath', '-w', str(path)]).decode().strip()


@dataclass
class UrlCache:
    strip_prefixes = ["download_blender_org_release_"]

    cache_folder: Path = Path("/extra/temp/blenderInstall/")

    def __post_init__(self) -> None:
        self.cache_folder.mkdir(parents=True, exist_ok=True)

    def url_to_filename(self, url: str, ext: str = "") -> str:
        # Remove the scheme (http, https) and replace unsupported characters
        url_parts = url.split('://')[-1]
        url_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', url_parts)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:6]

        # Strip any prefixes listed in strip_prefixes
        for prefix in self.strip_prefixes:
            if url_clean.startswith(prefix):
                url_clean = url_clean[len(prefix) :]

        filename = f"{url_clean[:50]}_{url_hash}{ext}"

        return filename

    def get_file_path(self, filename: str) -> Path:
        return self.cache_folder / filename

    def get_file(self, url: str, ext: str = "") -> Path:
        filename = self.url_to_filename(url, ext)
        filepath = self.get_file_path(filename)

        if not filepath.exists():
            print(url)
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad status codes
            content = response.content

            # Save the downloaded content to the cache
            with open(filepath, 'wb') as file:
                file.write(content)

        return filepath

    def invalidate(self, url: str, ext: str = "") -> None:
        self.get_file_path(self.url_to_filename(url, ext)).unlink(missing_ok=True)

    def invalidate_text(self, url: str) -> None:
        self.invalidate(url, ".html")

    def get_text(self, url: str) -> str:
        filepath = self.get_file(url, ".html")

        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()

    def get_binary(self, url: str) -> bytes:
        filepath = self.get_file(url)

        with open(filepath, 'rb') as file:
            return file.read()


url_cache = UrlCache()


@dataclass
class HtmlPage:
    html: str
    url: str = ""

    RELEASES_URL = "https://download.blender.org/release"

    @cached_property
    def soup(self) -> BeautifulSoup:
        # soup = BeautifulSoup(html_en, "html.parser")
        return BeautifulSoup(self.html, "html5lib")
        # soup = BeautifulSoup(html_en, "lxml")

    @staticmethod
    def of_file(html_path: Path) -> 'HtmlPage':
        with html_path.open('r', encoding='utf-8') as file:
            html_content = file.read()
        return HtmlPage(html=html_content)

    @staticmethod
    def of_url(url: str) -> 'HtmlPage':
        html = url_cache.get_text(url)
        return HtmlPage(html=html, url=url)

    @staticmethod
    def releases_list_page() -> 'HtmlPage':
        return HtmlPage.of_url(HtmlPage.RELEASES_URL)


@dataclass
class BlenderInstallation:
    ver_main_str: str
    platform_str: str
    ver_minor_str: str = "0"
    file_ext: str = ""
    url: str = ""

    @property
    def ver_minor(self) -> int:
        try:
            return int(self.ver_minor_str)
        except:
            return 0

    @cached_property
    def ver(self) -> tuple[int, int, int]:
        mj, mv = self.ver_main_str.split(".")
        return (int(mj), int(mv), self.ver_minor)

    @cached_property
    def ver_str(self) -> str:
        return ".".join([str(v) for v in self.ver])

    @property
    def install_file_name(self) -> str:
        return self.url.split('/')[-1]

    @property
    def is_windows(self) -> bool:
        return "indows" in self.platform_str

    def download_blender_install_file_path(self) -> Path:
        return url_cache.get_file(self.url, f".{self.file_ext}")

    @staticmethod
    def parse_main_version(name: str) -> tuple[str, str]:
        pattern = re.compile(r"blender(?:-|)(?P<ver_main>\d+\.\d+)")
        match = pattern.search(name)
        if not match:
            return None, None
        return match.group(0), match.group("ver_main")

    @staticmethod
    def of_name(name: str) -> Optional['BlenderInstallation']:
        name = name.lower()
        ver_main_match, ver_main = BlenderInstallation.parse_main_version(name)
        if not ver_main:
            return None
        remaining_name = name[len(ver_main_match) :]
        pattern = re.compile(r"[.]?(?P<ver_minor>[a-zA-Z0-9]+)?" r"(?:[.-](?P<platform>[a-zA-Z0-9\-]+))?" r"(?:[.](?P<file_extension>[a-zA-Z0-9.]+))?$")

        match = pattern.search(remaining_name)
        if not match:
            return None

        ver_minor = match.group("ver_minor") if match.group("ver_minor") else None
        platform = match.group("platform") if match.group("platform") else None
        file_extension = match.group("file_extension") if match.group("file_extension") else None
        return BlenderInstallation(
            ver_main_str=ver_main,
            platform_str=platform,
            ver_minor_str=ver_minor,
            file_ext=file_extension,
        )


@dataclass
class BlenderInstallator:
    install_root: Path = Path("/tmp/work/blender")

    def __post_init__(self) -> None:
        self.install_root.mkdir(parents=True, exist_ok=True)

    def list_available_main_versions(self) -> list[BlenderInstallation]:
        page: HtmlPage = HtmlPage.releases_list_page()
        page_links = page.soup.find_all("a")
        assert len(page_links) > 2

        installations = []
        for link in page_links:
            url: str = link.get('href', '')
            if not url.endswith("/"):
                continue
            installation = BlenderInstallation.of_name(url)
            if installation:
                installation.url = page.url + "/" + url
                installations.append(installation)
        return installations

    def list_all_available_versions(self, main_versions: list[BlenderInstallation]) -> list[BlenderInstallation]:
        ret: list[BlenderInstallation] = []
        for mv in main_versions:
            page: HtmlPage = HtmlPage.of_url(mv.url)
            page_links = page.soup.find_all("a")
            assert len(page_links) > 1

            for link in page_links:
                url: str = link.get('href', '')
                if url.endswith("md5") or url.endswith("sha256"):
                    continue
                installation = BlenderInstallation.of_name(url)
                if installation:
                    installation.url = mv.url + url
                    ret.append(installation)
        return ret

    def available_versions(self, min_major: int = 3) -> list[BlenderInstallation]:
        mvs = [mv for mv in self.list_available_main_versions() if mv.ver[0] >= min_major]
        return self.list_all_available_versions(mvs)

    def versions_for_test(self, min_major: int = 3) -> list[BlenderInstallation]:
        bis = [
            bv
            for bv in self.available_versions(min_major)
            if bv.platform_str and "win" in bv.platform_str and "arm" not in bv.platform_str and bv.file_ext == "zip"
        ]
        bis.sort(key=lambda bv: bv.ver)
        # Latest minor version in each major.main ver
        return [max(group, key=lambda bv: bv.ver) for _, group in groupby(bis, key=lambda bv: bv.ver[:2])]

    def versions_for_download(self, min_major: int = 5) -> list[BlenderInstallation]:
        bis = [
            bv
            for bv in self.available_versions(min_major)
            if bv.platform_str and "linux" in bv.platform_str and "x64" in bv.platform_str and bv.file_ext == "tar.xz" and bv.ver_minor_str.isdigit()
        ]
        if not bis:
            return []
        return [max(bis, key=lambda bv: bv.ver)]

    def refresh_cache(self, min_major: int = 4) -> None:
        """Drop cached release pages for Blender majors >= min_major so new releases become visible."""
        url_cache.invalidate_text(HtmlPage.RELEASES_URL)
        for mv in self.list_available_main_versions():
            if mv.ver[0] >= min_major:
                url_cache.invalidate_text(mv.url)

    def installation_path(self, bi: BlenderInstallation) -> Path:
        return self.install_root / f"blender-{bi.ver_str}-{bi.platform_str}"

    def exe_path(self, bi: BlenderInstallation) -> Path:
        if bi.is_windows:
            return self.installation_path(bi) / "blender.exe"
        return self.installation_path(bi) / "blender"

    def python_root_path(self, bi: BlenderInstallation) -> Path:
        return self.installation_path(bi) / bi.ver_main_str / "python" / "bin"

    def python_exe_path(self, bi: BlenderInstallation) -> Path:
        if bi.is_windows:
            return self.python_root_path(bi) / "python.exe"
        else:
            return self.python_root_path(bi) / "python"

    def is_installed(self, bi: BlenderInstallation) -> bool:
        return self.exe_path(bi).exists()

    def ensure_executable(self, path: Path) -> None:
        if not path.exists():
            raise RuntimeError(f"No file found at {path}")
        path.chmod(path.stat().st_mode | 0o111)  # Add executable flag

    def install(self, bi: BlenderInstallation) -> None:
        if self.is_installed(bi):
            raise RuntimeError(f"Blender version {bi.ver_str} is already installed in {self.installation_path(bi)}")

        zip_file_path = bi.download_blender_install_file_path()
        # install_path = self.installation_path(bi)
        install_path = self.install_root  # Zip file already contains folder, try to match it
        print(f"Installing {zip_file_path} to {install_path}")
        install_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(install_path)
        self.ensure_executable(self.exe_path(bi))
        assert self.is_installed(bi)

    def ensure_installed(self, bi: BlenderInstallation) -> None:
        if self.is_installed(bi):
            print(f"{bi.ver_str} already installed")
        else:
            self.install(bi)
        # v.installation_path = self.installation_path

    def run_python(self, bi: BlenderInstallation, *args: str) -> subprocess.CompletedProcess:
        cmd = [str(self.python_exe_path(bi)), *args]
        print(" ".join(cmd))
        return subprocess.run(cmd, check=True)

    def ensure_pip(self, bi: BlenderInstallation) -> None:
        python_exe = self.python_exe_path(bi)
        if not python_exe.exists():
            raise RuntimeError(f"No python found in the {python_exe}")
        self.ensure_executable(python_exe)
        self.run_python(bi, "-m", "ensurepip")

    def is_pytest_installed(self, bi: BlenderInstallation) -> bool:
        cmd = [str(self.python_exe_path(bi)), "-m", "pip", "list"]
        print(" ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        return "pytest" in result.stdout

    def ensure_pytest(self, bi: BlenderInstallation) -> None:
        if self.is_pytest_installed(bi):
            print("pytest already installed")
            return
        self.ensure_pip(bi)
        self.run_python(bi, "-m", "pip", "install", "pytest")
        assert self.is_pytest_installed(bi)


@dataclass
class BlenderSetup:
    installator: BlenderInstallator
    installation: BlenderInstallation
    config_root_path: Path = field(init=False)
    addon_src: Path = Path(pathlib.Path(__file__).parent.parent)

    def __post_init__(self) -> None:
        pf = f"blender_cfg-{self.installation.ver_str}-{self.installation.platform_str}_"
        # self.config_root_path = Path(tempfile.mkdtemp(prefix=pf))
        self.config_root_path = Path("/tmp/work/blender_cfg") / pf

    @cached_property
    def user_dir(self) -> Path:
        return self.config_root_path / "blender" / self.installation.ver_main_str

    @cached_property
    def scripts_path(self) -> Path:
        return self.user_dir / "scripts"

    @cached_property
    def addons_path(self) -> Path:
        return self.scripts_path / "addons"

    @cached_property
    def test_results_path(self) -> Path:
        return self.addons_path / "test_results.json"

    @cached_property
    def test_script_path(self) -> Path:
        return self.addons_path / "run_within_blender.py"

    def blender_env(self) -> dict[str, str]:
        """Env for the Blender run, with user data dirs isolated per version and platform."""
        if self.installation.is_windows:
            return {
                **os.environ,
                "BLENDER_USER_RESOURCES": to_wine_path(self.user_dir),
                # Version <3.6 doesn't support BLENDER_USER_RESOURCES
                "BLENDER_USER_CONFIG": to_wine_path(self.user_dir / "config"),
                "BLENDER_USER_SCRIPTS": to_wine_path(self.scripts_path),
            }
        return {**os.environ, "XDG_CONFIG_HOME": str(self.config_root_path)}

    def install_addon_symlink(self) -> None:
        self.addons_path.mkdir(parents=True, exist_ok=True)
        target = self.addons_path / "rhubarb_lipsync"
        if not target.exists():
            os.symlink(self.addon_src / "rhubarb_lipsync", target)

    @cached_property
    def project_version(self) -> str:
        return project_cfg["project"]["version"]

    def current_dist_zip(self) -> Path:
        """The dist zip of the current project version for this platform."""
        dist = self.addon_src / 'dist'
        platform_str = self.installation.platform_str.lower()[:5]
        zip_files = [file for file in dist.glob("rhubarb_lipsync_ng-*.zip") if platform_str in file.name.lower()]
        if not zip_files:
            raise RuntimeError(f"No zip file found for platform {platform_str} in the {dist}")
        current = [file for file in zip_files if f"-{self.project_version}.zip" in file.name.lower()]
        if len(current) != 1:
            raise RuntimeError(
                f"Expected exactly 1 zip of the current project version {self.project_version} "
                f"(platform {platform_str}), found: {[f.name for f in zip_files]}. "
                f"Run scripts/package.py to build the current version."
            )
        return current[0]

    def install_addon(self) -> None:
        self.addons_path.mkdir(parents=True, exist_ok=True)
        target = self.addons_path / "rhubarb_lipsync"
        with zipfile.ZipFile(self.current_dist_zip(), 'r') as zip_ref:
            zip_ref.extractall(target.parent)

    def install_tests(self) -> None:
        test_files = list(self.addon_src.glob("tests/*.py"))
        for test_file in test_files:
            shutil.copy(test_file, self.addons_path)

        data_src = self.addon_src / "tests" / "data"
        data_dst = self.addons_path / "data"
        if data_dst.exists():
            shutil.rmtree(data_dst)
        shutil.copytree(data_src, data_dst)

        aud_file = self.addons_path / "aud.py"
        if aud_file.exists():
            aud_file.unlink()

    def setup_config(self) -> None:
        config_dir = self.user_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

    def print_banner(self) -> None:
        print(" ---------------------------------------------  ")

    def run_blender(self) -> None:
        if self.installation.is_windows:
            script = to_wine_path(self.test_script_path)
        else:
            script = str(self.test_script_path)
        cmd = [str(self.installator.exe_path(self.installation)), "--background", "--python", script]
        print(" ".join(cmd))
        self.print_banner()
        subprocess.run(cmd, check=True, env=self.blender_env())
        self.print_banner()

    def install_and_run(self) -> None:
        self.setup_config()
        self.install_addon()
        self.install_tests()
        if self.test_results_path.exists():
            self.test_results_path.unlink()
        self.run_blender()


@dataclass
class TestResult:
    """Test outcome of one Blender version, as written by run_within_blender.py."""
    blender_version: str
    system: str = "N/A"
    total_tests: Optional[int] = None
    total_passed: Optional[int] = None
    total_failed: Optional[int] = None
    total_errors: Optional[int] = None
    total_skipped: Optional[int] = None
    note: str = ""

    @classmethod
    def from_file(cls, path: Path, blender_version: str) -> "TestResult":
        if not path.exists():
            return cls(blender_version=blender_version, note="No result")
        return cls(**json.loads(path.read_text()))

    @property
    def ok(self) -> bool:
        return self.total_tests is not None and not (self.total_failed or self.total_errors)

    def fmt(self, count: Optional[int]) -> str:
        return "N/A" if count is None else str(count)

    def fmt_bad(self, count: Optional[int]) -> str:
        return self.fmt(count) if not count else f"{RED}{count}{RESET}"

    def to_row(self) -> list[str]:
        return [
            self.blender_version,
            self.system,
            self.fmt(self.total_tests),
            self.fmt(self.total_passed),
            self.fmt_bad(self.total_failed),
            self.fmt_bad(self.total_errors),
            self.fmt(self.total_skipped),
            f"{RED}{self.note}{RESET}" if self.note else "",
        ]


@dataclass
class ResultsTable:
    """Renders TestResults as an aligned table."""
    headers = ["Version", "System", "Total", "Passed", "Failed", "Errors", "Skipped", "Note"]

    results: list[TestResult] = field(default_factory=list)

    def print(self) -> None:
        if not self.results:
            print("No results to display.")
            return

        table = [self.headers, *[r.to_row() for r in self.results]]
        # Calculate the width of each column, ignoring ANSI escape sequences
        col_widths = [max(len(strip_ansi(str(item))) for item in col) for col in zip(*table)]
        separator = "─" * (sum(col_widths) + 3 * (len(col_widths) - 1))

        print(separator)
        for row_idx, row in enumerate(table):
            padded_row = []
            for col_idx, cell in enumerate(row):
                padding = col_widths[col_idx] - len(strip_ansi(str(cell)))
                padded_row.append(f"{cell}{' ' * padding}")
            print(" │ ".join(padded_row))
            if row_idx == 0:
                print(separator)
        print(separator)


README_PATH = Path(__file__).parents[1] / "README.md"

README_TABLE_RX = re.compile(r"^\|\s*Version\b")
README_VER_CELL_RX = re.compile(r"\*\*(?P<maj>\d+)\.(?P<min>\d+)\*\*\.(?P<patch>\d+)")


def version_tuple(ver_str: str) -> tuple[int, int, int]:
    parts = [int(p) for p in ver_str.split()[0].split(".")]
    return parts[0], parts[1], parts[2]


@dataclass
class ReadmeRow:
    ver: tuple[int, int, int]
    cells: list[str]  # [Version, System, Total, Passed, Failed, Errors, Skipped, Status]

    @classmethod
    def parse(cls, line: str) -> Optional["ReadmeRow"]:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        m = README_VER_CELL_RX.search(cells[0])
        if not m:
            return None
        return cls((int(m["maj"]), int(m["min"]), int(m["patch"])), cells)

    @classmethod
    def of_result(cls, result: TestResult, old: Optional["ReadmeRow"]) -> "ReadmeRow":
        ver = version_tuple(result.blender_version)
        # Preserve the existing version cell verbatim (bold + LTS marker)
        version_cell = old.cells[0] if old else f"**{ver[0]}.{ver[1]}**.{ver[2]}" + (" LTS" if "LTS" in result.blender_version else "")
        return cls(
            ver,
            [
                version_cell,
                result.system,
                result.fmt(result.total_tests),
                result.fmt(result.total_passed),
                result.fmt(result.total_failed),
                result.fmt(result.total_errors),
                result.fmt(result.total_skipped),
                "✔️" if result.ok else "❌",
            ],
        )


def update_readme_table(readme_path: Path, results: list[TestResult]) -> None:
    """Refresh/add rows of the 'Supported Blender versions' table from actual test results."""
    lines = readme_path.read_text().splitlines()
    start = next((i for i, line in enumerate(lines) if README_TABLE_RX.match(line)), None)
    if start is None:
        raise RuntimeError(f"No version table found in {readme_path}")
    end = start + 1
    while end < len(lines) and lines[end].startswith("|"):
        end += 1

    rows = {r.ver: r for r in (ReadmeRow.parse(l) for l in lines[start + 2 : end]) if r}
    for result in results:
        ver = version_tuple(result.blender_version)
        rows[ver] = ReadmeRow.of_result(result, rows.get(ver))
    table_rows = sorted(rows.values(), key=lambda r: r.ver, reverse=True)

    header = ["Version", "System", "Total", "Passed", "Failed", "Errors", "Skipped", "Status"]
    table = [header, *[r.cells for r in table_rows]]
    widths = [max(len(c) for c in col) for col in zip(*table)]
    separator = "|" + "|".join("-" * (w + 2) for w in widths) + "|"

    def fmt(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

    new_table = [fmt(header), separator, *(fmt(r.cells) for r in table_rows)]
    readme_path.write_text("\n".join([*lines[:start], *new_table, *lines[end:]]) + "\n")


@dataclass
class Cli:
    count: Optional[int] = 2
    refresh: Optional[int] = None
    update_readme: bool = False
    installator: BlenderInstallator = field(default_factory=BlenderInstallator)
    results: ResultsTable = field(default_factory=ResultsTable)

    @staticmethod
    def parse_version_count(value: str) -> Optional[int]:
        if value.strip().lower() in ("all", "-1"):
            return None
        count = int(value)
        if count < 0:
            raise argparse.ArgumentTypeError(f"Expected a non-negative count, 'all' or -1, got {value!r}")
        return count

    @classmethod
    def parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Run the add-on unittest suite across Blender versions.")
        parser.add_argument(
            "-n",
            "--count",
            type=cls.parse_version_count,
            default=2,
            help="Number of newest Blender versions to test. Use 0 for none, 'all' or -1 for all. Default: 2",
        )
        parser.add_argument(
            "-r",
            "--refresh",
            type=int,
            nargs="?",
            const=4,
            default=None,
            metavar="MIN_MAJOR",
            help="Drop cached Blender release pages for majors >= MIN_MAJOR (default: 4) before running.",
        )
        parser.add_argument(
            "-u",
            "--update-readme",
            action="store_true",
            help="Update the 'Supported Blender versions' table in README.md from the actual test results.",
        )
        return parser

    @classmethod
    def from_args(cls, argv: Optional[list[str]] = None) -> 'Cli':
        return cls(**vars(cls.parser().parse_args(argv)))

    def selected_versions(self) -> list[BlenderInstallation]:
        versions = list(reversed(self.installator.versions_for_test()))
        if self.count is None:
            return versions
        return versions[: self.count]

    def prefetch_linux_tarball(self) -> None:
        # Download & cache the latest Linux x64 tarball (Blender 5+)
        for bv in self.installator.versions_for_download():
            path = bv.download_blender_install_file_path()
            print(f"Cached {bv.ver_str} {bv.platform_str} -> {path}")

    def run_test_version(self, installation: BlenderInstallation) -> None:
        print(f"{installation.ver} {installation.platform_str} {installation.file_ext} {installation.install_file_name}")
        self.installator.ensure_installed(installation)
        self.installator.ensure_pytest(installation)
        setup = BlenderSetup(self.installator, installation)
        setup.install_and_run()
        self.results.results.append(TestResult.from_file(setup.test_results_path, installation.ver_str))

    def run(self) -> None:
        if self.refresh is not None:
            print(f"Refreshing cached release pages for Blender {self.refresh}+")
            self.installator.refresh_cache(self.refresh)

        versions = self.selected_versions()
        if not versions:
            print("No Blender versions selected for testing.")
            return

        self.prefetch_linux_tarball()

        print(f"Testing {len(versions)} Blender version(s)")
        for installation in versions:
            self.run_test_version(installation)
        self.results.print()
        if self.update_readme:
            update_readme_table(README_PATH, self.results.results)
            print(f"Updated the Blender versions table in {README_PATH}")


if __name__ == "__main__":
    Cli.from_args().run()
