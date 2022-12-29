from functools import cache, cached_property
from pathlib import Path
from config import rhubarb_cfg
import urllib.request
import shutil
import hashlib
import zipfile
import os


def sha256(filename: Path) -> str:
    """ https://www.quickprogrammingtips.com/python/how-to-calculate-sha256-hash-of-a-file-in-python.html """
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


def download(url: str, dest_path: Path):
    """ https://stackoverflow.com/questions/7243750/download-file-from-web-in-python-3# """
    with urllib.request.urlopen(url) as response:
        with open(dest_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)


class RhubarbBinary:

    def __init__(self, cfg: dict, platform_cfg: dict):
        assert cfg and cfg["download"] and cfg["platforms"]
        self.cfg = cfg
        self.platform_cfg: dict = platform_cfg

    # @staticmethod
    # def executable_default_basename():
    #    return "rhubarb.exe" if platform.system() == "Windows" else "rhubarb"

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
    def executable_path(self) -> Path:
        return self.unziped_dir / self.executable_name

    @cached_property
    def expected_exe_sha256(self) -> Path:
        return self.platform_cfg["executable_sha256"]

    def rm_unzipped(self):
        """This will delete the whole where the zip was unzipped."""
        if not Path.exists(self.unziped_dir):
            return
        print(f"Deleting {self.unziped_dir}")
        shutil.rmtree(self.unziped_dir)

    def unzip(self):
        self.rm_unzipped()

        print(f"Unzipping the binaries for the {self.platform_cfg['name']} platform into {self.download_dir} ")
        with zipfile.ZipFile(self.download_file, 'r') as zip:
            zip.extractall(self.download_dir)

    def ensure_download(self, force=False) -> bool:
        if self.download_file.exists() and not force:
            return False
        self.download_dir.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {self.download_url} to \n {self.download_dir}")
        download(self.download_url, self.download_file)
        return True

    def ensure_unzipped(self, force=False) -> bool:
        if self.executable_path.exists() and not force:
            return False
        self.unzip()
        return True

    def verify_download_checksum(self):
        checksum = sha256(self.download_file)
        if checksum != self.expected_download_sha256:
            raise ValueError(f"""The checksum 
            {checksum} of the downloaded file 
            {self.download_file} 
            doesn't match the expected value:
            {self.expected_download_sha256}.
            Delete the .zip file to force re-download. Or update the expected checksum in the pyproject.toml """)

    def __repr__(self) -> str:
        return f"{self.zip_file_name}"

    @staticmethod
    def download_and_deploy_all():
        for b in RhubarbBinary.all_platforms(rhubarb_cfg):
            b.ensure_download()
            b.verify_download_checksum()
            b.ensure_unzipped()
            assert b.executable_path.exists()


if __name__ == '__main__':
    RhubarbBinary.download_and_deploy_all()

    print("Done")
