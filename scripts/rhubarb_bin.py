import filecmp
import hashlib
import platform
import re
import shutil
import urllib.request
import zipfile
from functools import cache, cached_property
from pathlib import Path

from config import rhubarb_cfg


def sha256(filename: Path) -> str:
    """https://www.quickprogrammingtips.com/python/how-to-calculate-sha256-hash-of-a-file-in-python.html"""
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


def download(url: str, dest_path: Path):
    """https://stackoverflow.com/questions/7243750/download-file-from-web-in-python-3#"""
    with urllib.request.urlopen(url) as response:
        with open(dest_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)


class RhubarbBinary:
    """
    Represents the rhubarb executable file and its resources. For a single platform (Linux/Win/macOs).
    Handles downloading/unzipping the rhubarb-lipsync release from github. Creates the /bin folder for the current platforms.
    Configuration is inside the pyproject.toml
    """

    include_file_list = [r"^[^/]+/[^/]+$", r"/res/"]  # All file in the root folder
    include_file_list_rx = [re.compile(pat, re.IGNORECASE) for pat in include_file_list]

    def __init__(self, cfg: dict, platform_cfg: dict) -> None:
        assert cfg and cfg["download"] and cfg["platforms"]
        self.cfg = cfg
        self.platform_cfg: dict = platform_cfg

    @staticmethod
    def all_platforms(cfg: dict) -> list['RhubarbBinary']:
        return [RhubarbBinary(cfg, p) for p in cfg["platforms"]]

    @property
    def base_url(self) -> str:
        return self.cfg["download"]["base_url"]

    @property
    def base_name(self) -> str:
        return self.cfg["download"]["base_name"]

    @property
    def expected_download_sha256(self) -> str:
        return self.platform_cfg["download_sha256"]

    @property
    def executable_name(self) -> str:
        return self.platform_cfg["executable_name"]

    @property
    def version(self) -> str:
        return self.cfg["download"]["version"]

    @cached_property
    def file_name(self) -> str:
        # Rhubarb-Lip-Sync-1.13.0-Linux
        return f"{self.base_name}-{self.version}-{self.platform_cfg['name']}"

    @cached_property
    def system_names(self) -> list[str]:
        """Mapping of the platfrom names (platform.system()) used for this config"""
        return self.platform_cfg['system_names']

    @cached_property
    def zip_file_name(self) -> str:
        # Rhubarb-Lip-Sync-1.13.0-Linux.zip
        return f"{self.file_name}.zip"

    @cached_property
    def download_url(self) -> str:
        # https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.13.0/Rhubarb-Lip-Sync-1.13.0-Linux.zip
        return f"{self.base_url}/v{self.version}/{self.zip_file_name}"

    @cached_property
    def project_dir(self) -> Path:
        return Path(__file__).parents[1]

    @cached_property
    def download_dir(self) -> Path:
        return self.project_dir / "download"

    @cached_property
    def download_file(self) -> Path:
        return self.download_dir / self.zip_file_name

    @cached_property
    def unziped_dir(self) -> Path:
        # Zip contains a subfolder named same as the zip, unzip directy to the download folder
        return self.download_dir / self.file_name

    @cached_property
    def executable_path_unzipped(self) -> Path:
        """Executable file path inside the project download folder"""
        return self.unziped_dir / self.executable_name

    @cached_property
    def bin_dir(self) -> Path:
        return self.project_dir / "rhubarb_lipsync" / "bin"

    @cached_property
    def executable_path(self) -> Path:
        """Executable file path inside the bin folder. This is the one to be shipped with plugin"""
        return self.bin_dir / self.executable_name

    def ensure_download(self, force=False) -> bool:
        if self.download_file.exists() and not force:
            return False
        self.download_dir.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {self.download_url} to \n {self.download_dir}")
        download(self.download_url, self.download_file)
        return True

    def verify_download_checksum(self) -> None:
        checksum = sha256(self.download_file)
        if checksum != self.expected_download_sha256:
            raise ValueError(
                f"""The checksum 
            {checksum} of the downloaded file 
            {self.download_file} 
            doesn't match the expected value:
            {self.expected_download_sha256}.
            Delete the .zip file to force re-download. Or update the expected checksum in the pyproject.toml """
            )

    def ensure_unzipped(self, force=False) -> bool:
        if self.executable_path_unzipped.exists() and not force:
            return False
        self.unzip()
        return True

    def rm_unzipped(self) -> None:
        """This will delete the whole platform-folder where the zip was unzipped."""
        if not Path.exists(self.unziped_dir):
            return
        print(f"Deleting {self.unziped_dir}")
        shutil.rmtree(self.unziped_dir)

    def unzip(self) -> None:
        self.rm_unzipped()
        print(f"Unzipping the binaries for the {self.platform_cfg['name']} platform into {self.download_dir} ")
        with zipfile.ZipFile(self.download_file, 'r') as zip:
            # Only files matching any of the file_list patterns
            fl = [fn for fn in zip.filelist if any((rx.search(fn.filename) for rx in RhubarbBinary.include_file_list_rx))]
            zip.extractall(self.download_dir, fl)

    def rm_bin(self) -> None:
        """This will delete the whole project's bin folder"""
        if not Path.exists(self.bin_dir):
            return
        print(f"Deleting {self.bin_dir}")
        shutil.rmtree(self.bin_dir)

    def is_deployed_to_bin(self) -> bool:
        """Whether is this RhubarbBinary platform currently deployed to the bin folder"""
        if not self.executable_path.exists():
            return False  # The bin/rhubar file don't even exists
        return filecmp.cmp(self.executable_path, self.executable_path_unzipped)

    def deploy_to_bin(self) -> None:
        self.rm_bin()
        print(f"Deploying {self.platform_cfg['name']} binary to {self.bin_dir} ")
        shutil.copytree(self.unziped_dir, self.bin_dir)

    def matches_platform(self, platfrom: str) -> bool:
        """Whether this RhubarbBinary matches the provided system platfrom name (Windows, Linux..)"""
        return platfrom in self.system_names

    @staticmethod
    def download_all_and_deploy(deploy_platform=platform.system()) -> None:
        platform_matched_count = 0
        for b in RhubarbBinary.all_platforms(rhubarb_cfg):
            b.ensure_download()
            b.verify_download_checksum()
            b.ensure_unzipped()
            assert b.executable_path_unzipped.exists()

            if b.matches_platform(deploy_platform):
                if not b.is_deployed_to_bin():
                    b.deploy_to_bin()
                assert b.executable_path.exists()
                platform_matched_count += 1
        if deploy_platform is not None:
            if platform_matched_count != 1:
                raise ValueError(
                    f"""Failed to deploy the binary for the requested `{deploy_platform}` platform. 
                Either the platform is not supported or the `system_names` mapping in the `pyproject.toml` needs to be extended. """
                )


if __name__ == '__main__':
    RhubarbBinary.download_all_and_deploy()

    print("Done")
