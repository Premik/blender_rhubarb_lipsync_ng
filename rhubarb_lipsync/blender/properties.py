import pathlib
import bpy
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty
from bpy.types import Object, PropertyGroup, Context, SoundSequence, Sound, AddonPreferences
from typing import Optional, cast
from rhubarb_lipsync.rhubarb.rhubarb_command_handling import RhubarbCommandWrapper, RhubarbParser
import pathlib


class RhubarbAddonPreferences(AddonPreferences):
    bl_idname = 'rhubarb_lipsync'

    @staticmethod
    def addons_path() -> pathlib.Path:
        return pathlib.Path(bpy.utils.user_resource('SCRIPTS', path="addons"))

    @staticmethod
    def default_executable_path() -> pathlib.Path:
        exe = RhubarbCommandWrapper.executable_default_filename()
        return RhubarbAddonPreferences.addons_path() / RhubarbAddonPreferences.bl_idname / exe

    executable_path_string: StringProperty(  # type: ignore
        name="Rhubarb lipsync executable",
        subtype='FILE_PATH',
        default=default_executable_path(),
    )

    @property
    def executable_path(self) -> pathlib.Path:
        if not self.executable_path_string:
            return None  # type: ignore
        return pathlib.Path(self.executable_path_string)

    recognizer: EnumProperty(  # type: ignore
        name="Recognizer",
        items=[
            ("pocketSphinx", "pocketSphinx", "PocketSphinx is an open-source speech recognition library that generally gives good results for English."),
            ("phonetic", "phonetic", "This recognizer is language-independent. Use it if your recordings are not in English."),
        ],
        default="pocketSphinx",
    )


class CaptureProperties(PropertyGroup):

    sound: PointerProperty(type=bpy.types.Sound, name="Sound")  # type: ignore
    start_frame: FloatProperty(name="Start frame", default=0)  # type: ignore

    @staticmethod
    def from_context(ctx: Context) -> 'CaptureProperties':
        if not ctx.object:
            return None  # type: ignore
        # Seems to data-block properties are lazily created
        # and doesn't exists until accessed for the first time
        # if not 'rhubarb_lipsync' in self.ctx.active_object:
        try:
            p = ctx.object.rhubarb_lipsync  # type: ignore
        except AttributeError:
            return None  # type: ignore
        return p

    def find_strips_of_sound(self, context: Context, limit=0) -> list[SoundSequence]:
        '''Finds a sound strip which is using the selected sounds.'''
        exact_match: list[SoundSequence] = []
        name_match: list[SoundSequence] = []
        if not self.sound:
            return []

        for i, sq in enumerate(context.scene.sequence_editor.sequences_all):
            if limit > 0 and i > limit:
                break  # Limit reached, break the search (for performance reasons)
            if not hasattr(sq, "sound"):
                continue  # Not a sound strip
            ssq = cast(SoundSequence, sq)
            foundSnd = ssq.sound
            if foundSnd is None:
                continue  # An empty strip
            if self.sound == foundSnd:
                name_match += [ssq]
                continue
            if self.sound.filepath == foundSnd.filepath:
                name_match += [ssq]
        return exact_match + name_match  # Exact matches first

    @property
    def sound_file_extension(self) -> str:
        if not self.sound:
            return ""
        path = pathlib.Path(self.sound.filepath)
        if not path:
            return ""
        sfx = path.suffix.lower()
        if not sfx:
            return ""
        if not sfx.startswith("."):
            return sfx
        return sfx[1:]  # Drop the trailing dot

    def is_sound_format_supported(self) -> bool:
        return self.sound_file_extension in ["ogg", "wav"]
