import pathlib
from functools import cached_property
from typing import Optional, cast

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty, CollectionProperty
from bpy.types import AddonPreferences, Context, PropertyGroup, Sound, UILayout
import math

from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandWrapper, RhubarbParser


class MouthCueListItem(PropertyGroup):
    key: StringProperty("key", description="Mouth cue key symbol (A,B,C..)")  # type: ignore
    start: FloatProperty(name="start", description="Start time of the cue")  # type: ignore
    end: FloatProperty(name="end", description="End time of the cue (usually matches start of the previous cue")  # type: ignore

    @cached_property
    def cue(self) -> MouthCue:
        return MouthCue(self.key, self.start, self.end)

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

    items: CollectionProperty(type=MouthCueListItem, name="Cue items")  # type: ignore

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

    def on_index_changed(self, context: Context) -> None:
        self.ensure_index_bounds()
        i = self.selected_item
        if not i:
            return
        frame, subframe = i.subframe(context)

        context.scene.frame_set(frame=frame, subframe=subframe)
        # context.scene.frame_float = i.frame_float

    index: IntProperty(name="Selected cue index", update=on_index_changed)  # type: ignore
    # index: IntProperty(name="Selected cue index")  # type: ignore


class CaptureProperties(PropertyGroup):

    sound: PointerProperty(type=bpy.types.Sound, name="Sound")  # type: ignore
    # start_frame: FloatProperty(name="Start frame", default=0)  # type: ignore
    dialog_file: StringProperty(  # type: ignore
        name="Dialog file",
        description="Additional plain-text file with transcription of the sound file to improve accuracy. Works for english only",
        subtype='FILE_PATH',
    )
    progress: IntProperty("progress", default=-1, min=0, max=100)  # type: ignore
    cue_list: PointerProperty(type=MouthCueList, name="Cues")  # type: ignore

    @staticmethod
    def from_context(ctx: Context) -> 'CaptureProperties':
        if not ctx.object:
            return None  # type: ignore
        # Seems the data-block properties are lazily created
        # and doesn't exist until accessed for the first time
        # if not 'rhubarb_lipsync' in self.ctx.active_object:
        try:
            p = ctx.object.rhubarb_lipsync  # type: ignore
        except AttributeError:
            return None  # type: ignore
        return p

    @staticmethod
    def context_selection_validation(ctx: Context) -> str:
        """Validates there is an active object with the rhubarb properties in the blender context"""
        if not ctx.object:
            return "No active object selected"
        if not CaptureProperties.from_context(ctx):
            return "'rhubarb_lipsync' not found on the active object"
        return ""

    def sound_selection_validation(context: Context, required_unpack=True) -> str:
        selection_error = CaptureProperties.context_selection_validation(context)
        if selection_error:
            return selection_error
        props = CaptureProperties.from_context(context)
        if not props.sound:
            return "No sound selected"
        sound: Sound = props.sound
        if required_unpack and sound.packed_file:
            return "Please unpack the sound first."
        return ""

    @property
    def sound_file_path(self) -> pathlib.Path:
        s: Sound = self.sound
        if not s or not s.filepath or s.packed_file:
            return None  # type: ignore
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
