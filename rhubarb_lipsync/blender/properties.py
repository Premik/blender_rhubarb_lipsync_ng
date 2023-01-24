import pathlib
import bpy
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, EnumProperty
from bpy.types import Object, PropertyGroup, Context, SoundSequence, Sound, AddonPreferences
from typing import Optional, cast
from rhubarb_lipsync.rhubarb.rhubarb_command_handling import RhubarbCommandWrapper, RhubarbParser
import pathlib


def addons_path() -> pathlib.Path:
    ap = bpy.utils.user_resource('SCRIPTS', path="addons")
    return pathlib.Path(ap)


def default_executable_path() -> pathlib.Path:
    exe = RhubarbCommandWrapper.executable_default_filename()
    return addons_path() / 'rhubarb_lipsync' / 'bin' / exe


class RhubarbAddonPreferences(AddonPreferences):
    bl_idname = 'rhubarb_lipsync'

    @staticmethod
    def from_context(ctx: Context) -> 'RhubarbAddonPreferences':
        addon = ctx.preferences.addons[RhubarbAddonPreferences.bl_idname]
        assert addon, f"The addon {RhubarbAddonPreferences.bl_idname} not found in the context."
        return cast(RhubarbAddonPreferences, addon.preferences)

    executable_path_string: StringProperty(  # type: ignore
        name="Rhubarb lipsync executable",
        subtype='FILE_PATH',
        default=str(default_executable_path()),
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

    info_panel_expanded: BoolProperty(default=True)  # type: ignore

    default_converted_output_folder: StringProperty(  # type: ignore
        name="Default output for converted files",
        description="Where to put the new wav/ogg files resulted from the conversion from an unsupported formats. Leave blank to use the source file's folder.",
        subtype='FILE_PATH',
        default="",
    )

    def new_command_handler(self):
        return RhubarbCommandWrapper(self.executable_path, self.recognizer)

    def draw(self, context: Context):
        layout = self.layout
        layout.prop(self, "executable_path_string")
        row = layout.row().split(factor=0.243)
        row.label(text="Rhubarb executable version:")

        # Hack to avoid circumvent circular imports
        import rhubarb_lipsync.blender.rhubarb_operators as rhubarb_operators

        ver = rhubarb_operators.GetRhubarbExecutableVersion.get_cached_value(context)
        if ver:  # Cached value, just show
            row.label(text=ver)
        else:  # Not cached, offer button
            row.operator(rhubarb_operators.GetRhubarbExecutableVersion.bl_idname)

        layout.prop(self, "recognizer")
        layout.prop(self, 'default_converted_output_folder')


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
