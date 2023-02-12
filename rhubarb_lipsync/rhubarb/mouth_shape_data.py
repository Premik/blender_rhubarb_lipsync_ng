import math
from functools import cache
from typing import Dict, List, Optional


class MouthShapeDescription:
    def __init__(self, key: str, short_dest: str = "", description: str = ""):
        self.key = key
        self.short_dest = short_dest
        self.description = description


key2mouth_shaped_desc = {
    # TODO Generate from md/html https://github.com/DanielSWolf/rhubarb-lip-sync#readme
    'A': MouthShapeDescription('A'),
    'B': MouthShapeDescription('B'),
    'C': MouthShapeDescription('C'),
    'D': MouthShapeDescription('D'),
    'E': MouthShapeDescription('E'),
    'F': MouthShapeDescription('F'),
    'G': MouthShapeDescription('G'),
    'H': MouthShapeDescription('H'),
    'X': MouthShapeDescription('X'),
}


class MouthCue:
    def __init__(self, key: str, start: float, end: float):
        global key2mouth_shaped_desc
        assert key in key2mouth_shaped_desc.keys(), f"The shape with the '{key}' key is unknown. Keys: {key2mouth_shaped_desc.keys()}"
        self.key = key
        self.start = float(start)
        self.end = float(end)

    @staticmethod
    def of_json(cue_json: Dict) -> 'MouthCue':
        return MouthCue(cue_json["value"], cue_json["start"], cue_json["end"])

    @staticmethod
    def time2frame(time: float, fps: int, fps_base=1.0) -> int:
        return int(round(MouthCue.time2subframe(time, fps, fps_base)))

    @staticmethod
    def time2subframe(time: float, fps: int, fps_base=1.0) -> float:
        assert fps > 0 and fps_base > 0, f"Can't convert to frame when fps is {fps}/{fps_base}"
        return time * fps / fps_base

    def start_frame(self, fps: int, fps_base=1.0) -> int:
        return MouthCue.time2frame(self.start, fps, fps_base)

    def start_subframe(self, fps: int, fps_base=1.0) -> float:
        return MouthCue.time2subframe(self.start, fps, fps_base)

    def __eq__(self, other):
        if not isinstance(other, MouthCue):
            return NotImplemented  # https://stackoverflow.com/questions/1227121/compare-object-instances-for-equality-by-their-attributes
        c = lambda a, b: math.isclose(a, b, abs_tol=0.001)
        o: MouthCue = other
        return self.key == o.key and c(self.start, o.start) and c(self.end, o.end)

    def __repr__(self) -> str:
        return f"'{self.key}' {self.start:0.2f}-{self.end:0.2f}"
