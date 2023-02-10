from functools import cached_property
import pathlib
import bpy
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, EnumProperty, IntProperty
from bpy.types import PropertyGroup, Context, UILayout, Sound, AddonPreferences
import bpy.utils.previews
from typing import Optional, cast
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandWrapper, RhubarbParser
import pathlib


class CaptureProperties(PropertyGroup):

    sound: PointerProperty(type=bpy.types.Sound, name="Sound")  # type: ignore
    # start_frame: FloatProperty(name="Start frame", default=0)  # type: ignore
    dialog_file: StringProperty(  # type: ignore
        name="Dialog file",
        description="Additional plain-text file with transcription of the sound file to improve accuracy. Works for english only",
        subtype='FILE_PATH',
    )
    progress: IntProperty("progress", default=-1, min=0, max=100)  # type: ignore

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
