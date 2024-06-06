import pathlib

import tomli

# https://realpython.com/python-toml/
# Helper module to load custom config directly from the pyproject.toml file


def load_project_cfg() -> dict:
    path = pathlib.Path(__file__).parent.parent / "pyproject.toml"
    with path.open(mode="rb") as fp:
        return tomli.load(fp)


def dist_zip_name(platform: str, ver: str) -> str:
    return f"rhubarb_lipsync_ng-{platform}-{ver}"


project_cfg = load_project_cfg()
rhubarb_cfg = project_cfg["tool"]["rhubarb_lipsync"]
