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
        return UrlCache.cache_folder / filename

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
        return HtmlPage.of_url("https://download.blender.org/release")


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
        pattern = re.compile(r"[.]?(?P<ver_minor>[a-zA-Z0-9]+)?" r"(?:[.-](?P<platform>[a-zA-Z0-9\-]+))?" r"(?:[.](?P<file_extension>[a-zA-Z0-9]+))?$")

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
    cache_folder: Path = Path("/extra/temp/blenderInstall/")
    # install_root: Path = Path("/var/wine/64loc/drive_c/blender")
    install_root: Path = Path("/tmp/work/blender")

    def __post_init__(self) -> None:
        self.cache_folder.mkdir(parents=True, exist_ok=True)
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

    def versions_for_test(self) -> list[BlenderInstallation]:
        bis: list[BlenderInstallation] = []
        for bv in bi.list_all_available_versions(bi.list_available_main_versions()):
            if "win" not in bv.platform_str:
                continue
            if "arm" in bv.platform_str:
                continue
            if bv.file_ext != "zip":
                continue
            v = bv.ver
            if v[0] < 3:
                continue
            bis.append(bv)

        bis.sort(key=lambda x: (x.ver[0], x.ver[1], x.ver[2]))
        bis_filtered = []
        for key, group in groupby(bis, key=lambda x: (x.ver[0], x.ver[1])):
            # Latest minor version in each major.main ver
            max_minor = max(group, key=lambda x: (x.ver[1], x.ver[2]))
            bis_filtered.append(max_minor)
        return bis_filtered

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

    def ensure_pip(self, bi: BlenderInstallation) -> None:
        python_exe = self.python_exe_path(bi)
        if not python_exe.exists():
            raise RuntimeError(f"No python found in the {python_exe}")
        self.ensure_executable(python_exe)
        cmd = f'''{python_exe} -m ensurepip'''
        print(cmd)
        os.system(cmd)

    def is_pytest_installed(self, bi: BlenderInstallation) -> bool:
        python_exe = self.python_exe_path(bi)
        cmd = f'''{python_exe} -m pip list'''
        print(cmd)
        result = os.popen(cmd).read()
        return 'pytest' in result

    def ensure_pytest(self, bi: BlenderInstallation) -> None:
        self.ensure_pip(bi)
        if self.is_pytest_installed(bi):
            print("pytest already installed")
            return
        python_exe = self.python_exe_path(bi)
        cmd = f'''{python_exe} -m pip install pytest'''
        print(f"Installing pytest with: {cmd}")
        os.system(cmd)
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

    def set_blender_user_data(self) -> None:
        if self.installation.is_windows:
            self.set_blender_user_data_windows()
        else:
            self.set_blender_user_data_nix()

    def set_blender_user_data_windows(self) -> None:
        os.environ["BLENDER_USER_RESOURCES"] = to_wine_path(self.user_dir)
        # Version <3.6 doesn't support BLENDER_USER_RESOURCES
        os.environ["BLENDER_USER_CONFIG"] = to_wine_path(self.user_dir / "config")
        os.environ["BLENDER_USER_SCRIPTS"] = to_wine_path(self.scripts_path)

        # print(f"User dir: {windows_path}")

    def set_blender_user_data_nix(self) -> None:
        os.environ["XDG_CONFIG_HOME"] = str(self.config_root_path)
        print(f"User dir: {self.config_root_path}")

    def install_addon_symlink(self) -> None:
        self.addons_path.mkdir(parents=True, exist_ok=True)
        target = self.addons_path / "rhubarb_lipsync"
        if not target.exists():
            os.symlink(self.addon_src / "rhubarb_lipsync", target)

    def install_addon(self) -> None:
        self.addons_path.mkdir(parents=True, exist_ok=True)
        target = self.addons_path / "rhubarb_lipsync"
        dist = self.addon_src / 'dist'

        platform_str = self.installation.platform_str.lower()[:5]
        zip_files = [file for file in dist.glob("rhubarb_lipsync_ng-*.zip") if platform_str in file.name.lower()]

        if len(zip_files) == 0:
            raise RuntimeError(f"No zip file found for platform {platform_str} in the {dist}")
        elif len(zip_files) > 1:
            raise RuntimeError(f"Multiple zip files found for platform {platform_str}: {zip_files} in the {dist}.")

        zip_file = zip_files[0]
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
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

    def run_blender_win(self) -> None:
        blender_exe_path = '"' + str(self.installator.exe_path(self.installation)) + '"'
        script = to_wine_path(self.test_script_path)
        # cmd = f'''wine {blender_exe_path} --background --python "{script}"'''
        cmd = f'''{blender_exe_path} --background --python "{script}"'''
        print(cmd)
        self.print_banner()
        os.system(cmd)
        self.print_banner()

    def run_blender_nix(self) -> None:
        cmd = f'''{self.installator.exe_path(self.installation)} --background --python "{self.test_script_path}"'''
        print(cmd)
        self.print_banner()
        os.system(cmd)
        self.print_banner()

    def run_blender(self) -> None:
        if self.installation.is_windows:
            self.run_blender_win()
        else:
            self.run_blender_nix()

    def add_result_header(self, results_table: list[list[str]]) -> None:
        headers = ["Version", "System", "Total", "Passed", "Failed", "Errors", "Skipped", "Note"]
        results_table.append(headers)

    def collect_result(self, results_table: list[list[str]]) -> None:
        RED = '\033[91m'
        RESET = '\033[0m'

        if not results_table:
            self.add_result_header(results_table)

        if not self.test_results_path.exists():
            results_table.append(["N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", f"{RED}No result{RESET}"])
            return

        with self.test_results_path.open('r') as file:
            test_results = json.load(file)

        blender_version = test_results.get("blender_version", "N/A")
        system = test_results.get("system", "N/A")
        total_tests = test_results.get("total_tests", "N/A")
        total_passed = test_results.get("total_passed", "N/A")
        total_failed = test_results.get("total_failed", "N/A")
        total_errors = test_results.get("total_errors", "N/A")
        total_skipped = test_results.get("total_skipped", "N/A")

        if total_failed > 0:
            failed = f"{RED}{total_failed}{RESET}"
        else:
            failed = "0"

        if total_errors > 0:
            errors = f"{RED}{total_errors}{RESET}"
        else:
            errors = "0"
        results_table.append([blender_version, system, str(total_tests), str(total_passed), failed, errors, str(total_skipped), ""])

    def install_and_run(self) -> None:
        self.setup_config()
        self.install_addon()
        self.install_tests()
        self.set_blender_user_data()
        if self.test_results_path.exists():
            self.test_results_path.unlink()
        self.run_blender()


def strip_ansi_sequences(text: str) -> str:
    ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)


def print_test_results_table(results_table: list[list[str]]) -> None:
    if not results_table:
        print("No results to display.")
        return

    # Calculate the width of each column, ignoring ANSI escape sequences
    col_widths = [max(len(strip_ansi_sequences(str(item))) for item in col) for col in zip(*results_table)]

    # Print the header separator
    print("─" * (sum(col_widths) + 3 * (len(col_widths) - 1)))

    # Print each row with proper formatting
    for row_idx, row in enumerate(results_table):
        padded_row = []
        for col_idx, cell in enumerate(row):
            stripped_cell = strip_ansi_sequences(cell)
            padding = col_widths[col_idx] - len(stripped_cell)
            padded_cell = f"{cell}{' ' * padding}"
            padded_row.append(padded_cell)

        # Print the row
        print(" │ ".join(padded_row))

        # Print a separator after the header row
        if row_idx == 0:
            print("─" * (sum(col_widths) + 3 * (len(col_widths) - 1)))

    # Print the footer separator
    print("─" * (sum(col_widths) + 3 * (len(col_widths) - 1)))


if __name__ == "__main__":
    # setup = BlenderSetup(root_path=Path("/tmp/work/fresh2"), )
    # setup = BlenderSetup(root_path=Path("/tmp/work/freshWin"), target_platform="Windows", blender_main_ver="3.5")
    # setup = BlenderSetup(root_path=Path("/tmp/work/freshWin"), target_platform="Windows", blender_main_ver="3.0")
    # setup = BlenderSetup(root_path=Path("/tmp/work/fresh"), target_platform="Linux", blender_ver="4.2")
    # setup.install_and_run()

    bi = BlenderInstallator()
    l = bi.versions_for_test()
    l.reverse()
    results_table: list[list[str]] = []
    for v in l:
        # print(f"{v.ver} {v.platform_str} {v.file_ext} {v.install_file_name}")
        # print(v.download_blender_install_file_path())
        # print(f"{v.ver} {bi.is_installed(v)} {bi.exe_path(v)}")
        bi.ensure_installed(v)
        bi.ensure_pytest(v)
        bs = BlenderSetup(bi, v)
        bs.install_and_run()
        bs.collect_result(results_table)
        break
    print_test_results_table(results_table)
