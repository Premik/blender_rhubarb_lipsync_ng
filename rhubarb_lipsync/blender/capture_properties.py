import bisect
import logging
import math
from operator import attrgetter, index
import pathlib
from functools import cached_property
from typing import Any, Callable, Optional, cast, Generator

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Action, AddonPreferences, Context, PropertyGroup, Sound, UILayout

from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfo, MouthShapeInfos
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob, RhubarbCommandWrapper, RhubarbParser
import re

log = logging.getLogger(__name__)


class MouthCueListItem(PropertyGroup):
    """A captured mouth cue."""

    key: StringProperty(  # type: ignore
        "key",
        description="Mouth cue key symbol (A,B,C..)",
        # get=lambda s: s.cue.key,
        # get=lambda s: s['key'],
        # set=lambda s, v: setattr(s.cue.key, v),
        # set=lambda s, v: s.gg(v),
    )
    start: FloatProperty(name="start", description="Start time of the cue")  # type: ignore
    end: FloatProperty(name="end", description="End time of the cue (usually matches start of the previous cue")  # type: ignore

    @cached_property
    def cue(self) -> MouthCue:
        return MouthCue(self.key, self.start, self.end)
        # print("New")
        # return MouthCue(self['key'], self['start'], self['end'])

    def set_from_cue(self, cue: MouthCue) -> None:
        self.key = cue.key
        self.start = cue.start
        self.end = cue.end

    def frame(self, ctx: Context) -> int:
        return self.cue.start_frame(ctx.scene.render.fps, ctx.scene.render.fps_base)

    def frame_float(self, ctx: Context) -> float:
        return self.cue.start_frame_float(ctx.scene.render.fps, ctx.scene.render.fps_base)

    def end_frame_float(self, ctx: Context) -> float:
        return self.cue.end_frame_float(ctx.scene.render.fps, ctx.scene.render.fps_base)

    def subframe(self, ctx: Context) -> tuple[int, float]:
        return self.cue.start_subframe(ctx.scene.render.fps, ctx.scene.render.fps_base)

    def frame_str(self, ctx: Context) -> str:
        if ctx.scene.show_subframe:
            return f"{self.frame_float(ctx):0.2f}"
        return f"{self.frame(ctx)}"

    @property
    def duration(self) -> float:
        return self.cue.end - self.cue.start

    def duration_frames(self, ctx: Context) -> int:
        return int(math.ceil(self.end_frame_float(ctx) - self.frame_float(ctx)))

    @property
    def time_str(self) -> str:
        return f"{self.start:0.2f}"

    @property
    def duration_str(self) -> str:
        return f"{self.duration:0.2f}"


class MouthCueList(PropertyGroup):
    """List of the captured mouth cues."""

    items: CollectionProperty(type=MouthCueListItem, name="Cue items")  # type: ignore

    # Autoload would fail in the typing reflection because of the 'MouthCueList' being unknown
    # index_changed: Callable[['MouthCueList', Context, MouthCueListItem], None] | None
    index_changed: Callable[[PropertyGroup, Context, MouthCueListItem], None]

    def add_cues(self, cues: list[MouthCue]) -> None:
        for cue in cues:
            item: MouthCueListItem = self.items.add()
            item.set_from_cue(cue)

    @property
    def index_within_bounds(self) -> int:
        l = len(self.items)
        if l == 0:
            return -1  # Empty list
        if self.index < 0:  # Befor the first
            return 0
        if self.index >= l:  # After the last
            return l - 1
        return self.index

    def ensure_index_bounds(self) -> None:
        new = self.index_within_bounds
        if self.index != new:
            self.index = new

    @property
    def selected_item(self) -> Optional[MouthCueListItem]:
        if self.index < 0 or self.index >= len(self.items):
            return None
        return self.items[self.index]

    def find_index_by_time(self, time: float) -> int:
        return bisect.bisect_right(self.items, time, key=attrgetter('start'))

    def find_cue_by_time(self, time: float) -> Optional[MouthCueListItem]:
        idx = self.find_index_by_time(time)
        if idx < 0 or idx >= len(self.items):
            return None
        return self.items[idx]

    def on_index_changed(self, context: Context) -> None:
        if not getattr(MouthCueList, 'index_changed', None):
            return
        self.ensure_index_bounds()
        i = self.selected_item
        if not i:
            return
        # prefs = RhubarbAddonPreferences.from_context(self.ctx)
        MouthCueList.index_changed(self, context, i)

        # context.scene.frame_float = i.frame_float

    index: IntProperty(name="Selected cue index", update=on_index_changed)  # type: ignore
    # index: IntProperty(name="Selected cue index")  # type: ignore


class JobProperties(PropertyGroup):
    """Describes current state of the capture-process"""

    progress: IntProperty("Progress", default=-1, min=0, max=100)  # type: ignore
    status: StringProperty("Capture status")  # type: ignore
    error: StringProperty("Error message")  # type: ignore
    cancel_request: BoolProperty(default=False, name="Cancel requested")  # type: ignore

    @property
    def running(self) -> bool:
        return self.progress > 0 and self.progress != 100

    def update_from_async_job(self, job: RhubarbCommandAsyncJob) -> None:
        self.progress = job.last_progress
        self.status = job.status
        if not job.last_exception:
            self.error = ""
        else:
            self.error = f"{type(job.last_exception).__name__}\n{' '.join(job.last_exception.args)}"


class CaptureProperties(PropertyGroup):
    """Capture setup and list of captured cues"""

    def on_sound_update(self, ctx: Context) -> None:
        # ctx.area.tag_redraw()
        rootProps = CaptureListProperties.from_context(ctx)
        rootProps.name_search = self.short_desc(rootProps.index)

    sound: PointerProperty(type=bpy.types.Sound, name="Sound", update=on_sound_update)  # type: ignore
    # start_frame: FloatProperty(name="Start frame", default=0)  # type: ignore
    dialog_file: StringProperty(  # type: ignore
        name="Dialog file",
        description="Additional plain-text file with transcription of the sound file to improve accuracy. Works for english only",
        subtype='FILE_PATH',
    )
    job: PointerProperty(type=JobProperties, name="Job")  # type: ignore
    cue_list: PointerProperty(type=MouthCueList, name="Cues")  # type: ignore
    # mapping: PointerProperty(type=MappingList, name="Mapping")  # type: ignore

    def sound_selection_validation(context: Context, required_unpack=True) -> str:
        # selection_error = MappingProperties.context_selection_validation(context)
        # if selection_error:
        #    return selection_error
        props = CaptureListProperties.capture_from_context(context)
        if not props.sound:
            return "No sound selected"
        sound: Sound = props.sound
        if required_unpack and sound.packed_file:
            return "Please unpack the sound first."
        return ""

    @property
    def sound_file_path(self) -> pathlib.Path | None:
        s: Sound = self.sound
        if not s or not s.filepath or s.packed_file:
            return None
        return pathlib.Path(self.sound.filepath)

    @property
    def sound_file_extension(self) -> str:
        p = self.sound_file_path
        if not p:
            return ""
        sfx = p.suffix.lower()
        if not sfx:
            return ""
        if not sfx.startswith("."):
            return sfx
        return sfx[1:]  # Drop the trailing dot

    @property
    def sound_file_basename(self) -> str:
        p = self.sound_file_path
        if not p:
            return ""
        return p.stem

    @property
    def sound_file_folder(self) -> str:
        p = self.sound_file_path
        if not p:
            return ""
        return str(p.parent)

    def is_sound_format_supported(self) -> bool:
        return self.sound_file_extension in ["ogg", "wav"]

    def get_sound_name_with_new_extension(self, new_ext: str) -> str:
        p = self.sound_file_basename
        assert p, "Can't change extension while sound file is not set"
        assert new_ext is not None
        return f"{p}.{new_ext.lower()}"

    def short_desc(self, indx: int):
        jprops: JobProperties = self.job
        if jprops and jprops.status:
            status = f" ({jprops.status})"
        else:
            status = ""

        if self.sound:
            fn = f"{self.sound_file_basename}.{self.sound_file_extension}"
        else:
            fn = "<No sound selected>"
        # return f"{fn}{status}.{str(indx).zfill(3)}"
        return f"{str(indx).zfill(3)} {fn}"


class CaptureListProperties(PropertyGroup):
    """List of capture setup and cues. Hooked to Blender scene"""

    search_index_re = re.compile(r"^(?P<idx>\d+\d+\d+)\s.*")

    items: CollectionProperty(type=CaptureProperties, name="Captures")  # type: ignore
    index: IntProperty(name="Selected capture index")  # type: ignore

    @property
    def name_search_index(self) -> int:
        if not self.name_search:
            return -1
        m = CaptureListProperties.search_index_re.search(self.name_search)
        if m is None:
            return -1
        idx = m.groupdict()["idx"]
        if idx is None:
            return -1
        return int(idx)

    def as_prop_search(self, ctx: Context, edit_text) -> Generator[str, Any, None]:
        rootProps = CaptureListProperties.from_context(ctx)
        caps: list[CaptureProperties] = rootProps and rootProps.items
        for i, p in enumerate(caps or []):
            yield p.short_desc(i)
            # yield (p.short_desc, str(i))
        # return [(m, str(i)) for i, m in enumerate(materials)]

    def sync_search_with_index(self, ctx: Context):
        items = list(self.as_prop_search(ctx, ""))
        if self.index < 0 or self.index >= len(self.items):
            v = ""
        else:
            v = items[self.index]
        if v != self.name_search:
            self.name_search = v

    def on_search_update(self, ctx: Context) -> None:
        # Change selected item based on the search(take index from the name sufx)
        idx = self.name_search_index
        if idx < 0:
            return
        if self.index == idx:
            return  # Already selected
        self.index = idx

    name_search: StringProperty(name="name_search", description="Selected capture", search=as_prop_search, update=on_search_update)  # type: ignore

    @property
    def selected_item(self) -> Optional[CaptureProperties]:
        if self.index < 0 or self.index >= len(self.items):
            return None
        return self.items[self.index]

    @staticmethod
    def from_context(ctx: Context) -> Optional['CaptureListProperties']:
        """Get the  properties from the current scene of the provided context"""

        if not ctx.scene:
            return None
        ret: CaptureListProperties = getattr(ctx.scene, 'rhubarb_lipsync_captures')  # type: ignore
        return ret

    @staticmethod
    def capture_from_context(ctx: Context) -> Optional['CaptureProperties']:
        cl = CaptureListProperties.from_context(ctx)
        if not cl:
            return None
        return cl.selected_item
