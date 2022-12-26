import pathlib
import tomli
from functools import cache

#https://realpython.com/python-toml/


def _load_project_cfg()->dict:
    path = pathlib.Path(__file__).parent.parent / "pyproject.toml"
    with path.open(mode="rb") as fp:
        return tomli.load(fp)


project_cfg=_load_project_cfg()
rhubarb_cfg=project_cfg["tool"]["rhubarb_lipsync"]
