import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
from bs4.element import Tag
import requests


def to_wine_path(path: Path) -> str:
    return subprocess.check_output(['winepath', '-w', str(path)]).decode().strip()


@dataclass
class UrlCache:
    cache_folder: Path = Path("/extra/temp/blenderInstall/")

    def __post_init__(self) -> None:
        self.cache_folder.mkdir(parents=True, exist_ok=True)

    def url_to_filename(self, url: str) -> str:
        # Remove the scheme (http, https) and replace unsupported characters
        url_parts = url.split('://')[-1]
        url_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', url_parts)
        url_hash = hashlib.md5(url.encode()).hexdigest()

        # Combine the cleaned URL and its hash
        filename = f"{url_clean[:50]}_{url_hash}.html"
        return filename

    def get_file_path(self, filename: str) -> Path:
        return UrlCache.cache_folder / filename

    def get_text(self, url: str) -> str:
        filename = self.url_to_filename(url)
        filepath = self.get_file_path(filename)

        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()

        # If the file does not exist in the cache, download it
        print(url)
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes
        text_content = response.text

        # Save the downloaded HTML to the cache
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(text_content)

        return text_content


@dataclass
class HtmlPage:
    url_cache = UrlCache()
    html: str

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
        html = HtmlPage.url_cache.get_text(url)
        return HtmlPage(html=html)

    @staticmethod
    def releases_list_page() -> 'HtmlPage':
        return HtmlPage.of_url(f"https://download.blender.org/release")

    @staticmethod
    def main_release_details_page(release_name: str) -> 'HtmlPage':
        return HtmlPage.of_url(f"https://download.blender.org/release/{release_name}/")


@dataclass
class BlenderInstallation:
    ver_main: str
    platform_str: str
    ver_minor: str = "0"
    url: str = ""

    @staticmethod
    def parse_main_version(name: str) -> str:
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
        pattern = re.compile(r"[.]?(?P<ver_minor>[a-zA-Z0-9]+)?" r"(?:[.-](?P<platform>[a-zA-Z0-9\-]+))?")

        match = pattern.search(remaining_name)
        if not match:
            return None

        ver_minor = match.group("ver_minor") if match.group("ver_minor") else None
        platform = match.group("platform") if match.group("platform") else None

        return BlenderInstallation(ver_main, platform, ver_minor)


@dataclass
class BlenderInstallator:
    cache_folder: Path = Path("/extra/temp/blenderInstall/")
    blender_min_ver: str = "0"

    def __post_init__(self) -> None:
        self.cache_folder.mkdir(parents=True, exist_ok=True)

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
                installation.url = url
                installations.append(installation)
        return installations

    def list_all_available_versions(self, main_versions: list[BlenderInstallation]) -> list[BlenderInstallation]:
        ret: list[BlenderInstallation] = []
        for mv in main_versions:
            page: HtmlPage = HtmlPage.main_release_details_page(mv.url)
            page_links = page.soup.find_all("a")
            assert len(page_links) > 1

            for link in page_links:
                url: str = link.get('href', '')
                if url.endswith("md5") or url.endswith("sha256"):
                    continue
                installation = BlenderInstallation.of_name(url)
                if installation:
                    ret.append(installation)
        return ret

    @cached_property
    def blender_full_ver(self) -> str:
        return f"{self.blender_main_ver}.{self.blender_min_ver}"

    @cached_property
    def blender_install_file_name(self) -> str:
        platform2fn = {
            'Windows': 'windows-x64',
            'Linux': 'linux-x64',
        }
        p = platform2fn[self.target_platform]
        return f"blender-{self.blender_full_ver}-{p}.zip"

    @cached_property
    def blender_download_url(self) -> str:
        r = "https://download.blender.org/release"
        return f"{r}/Blender{self.blender_main_ver}/{self.blender_install_file_name}"

    def get_cache_file_path(self, file_name: str) -> Path:
        return self.cache_folder / file_name

    @property
    def blender_install_file_path(self) -> Path:
        return self.get_cache_file_path(self.blender_install_file_name)

    def download_blender_install_file(self):
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes

        html_content = response.text

        # Save the downloaded HTML to the cache
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(html_content)

        return html_content


@dataclass
class BlenderSetup:
    root_path: Path = field(default_factory=lambda: Path(tempfile.mkdtemp(prefix="blenderFresh_")))
    target_platform: str = field(default_factory=lambda: platform.system())
    blender_main_ver: str = "4.2"

    addon_src: Path = Path(pathlib.Path(__file__).parent.parent)

    @cached_property
    def user_dir(self) -> Path:
        return self.root_path / "blender" / self.blender_main_ver

    @cached_property
    def addons_path(self) -> Path:
        return self.user_dir / "scripts" / "addons"

    @cached_property
    def test_results_path(self) -> Path:
        return self.addons_path / "test_results.json"

    def set_blender_user_data(self) -> None:
        if self.target_platform == "Windows":
            self.set_blender_user_data_windows()
        else:
            self.set_blender_user_data_nix()

    def set_blender_user_data_windows(self) -> None:
        windows_path = to_wine_path(self.user_dir)
        os.environ["BLENDER_USER_RESOURCES"] = windows_path
        print(f"User dir: {windows_path}")

    def set_blender_user_data_nix(self) -> None:
        os.environ["XDG_CONFIG_HOME"] = str(self.root_path)
        print(f"User dir: {self.root_path}")

    def install_addon(self) -> None:
        self.addons_path.mkdir(parents=True, exist_ok=True)
        target = self.addons_path / "rhubarb_lipsync"
        if not target.exists():
            os.symlink(self.addon_src / "rhubarb_lipsync", target)

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

    def run_blender(self) -> None:
        script_path = self.addons_path / "run_within_blender.py"
        # exe = 'blender-4.2'
        exe = 'wine "/var/wine/64loc/drive_c/Program Files/Blender Foundation/Blender 3.5/blender.exe"'
        script = to_wine_path(script_path)
        cmd = f'''{exe} --background --python "{script}"'''
        print(cmd)
        os.system(cmd)

    def verify_result(self) -> None:
        if not self.test_results_path.exists():
            raise FileNotFoundError(f"Test results file not found at {self.test_results_path}")

        with self.test_results_path.open('r') as file:
            test_results = json.load(file)

        total_tests = test_results.get("total_tests", 0)
        total_failed = test_results.get("total_failed", 0)

        if total_failed > 0:
            raise AssertionError(f"There are {total_failed} failed tests.")

        if total_tests < 44:
            raise AssertionError(f"Total tests are {total_tests}, expected at least 44 tests, seems some were skip")

        print("All checks passed.")

    def install_and_run(self) -> None:
        self.setup_config()
        self.install_addon()
        self.install_tests()
        self.set_blender_user_data()
        if self.test_results_path.exists():
            self.test_results_path.unlink()
        self.run_blender()
        self.verify_result()


if __name__ == "__main__":
    # setup = BlenderSetup(root_path=Path("/tmp/work/fresh2"), )
    # setup = BlenderSetup(root_path=Path("/tmp/work/freshWin"), target_platform="Windows", blender_main_ver="3.5")
    # setup = BlenderSetup(root_path=Path("/tmp/work/freshWin"), target_platform="Windows", blender_main_ver="3.0")
    # setup = BlenderSetup(root_path=Path("/tmp/work/fresh"), target_platform="Linux", blender_ver="4.2")
    # setup.install_and_run()
    bi = BlenderInstallator()
    for v in bi.list_all_available_versions(bi.list_available_main_versions()):
        print(f"{v.ver_main}.{v.ver_minor} {v.platform_str}")
