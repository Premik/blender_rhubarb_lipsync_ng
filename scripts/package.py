from functools import cached_property
from pathlib import Path
from config import rhubarb_cfg


class PackagePlugin:

    def __init__(self, cfg: dict):
        pass
    
    
if __name__ == '__main__':
    pp=PackagePlugin(rhubarb_cfg)

    print("Done")
