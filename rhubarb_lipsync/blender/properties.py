from functools import cached_property
import pathlib
import bpy
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, EnumProperty
from bpy.types import Object, PropertyGroup, Context, SoundSequence, Sound, AddonPreferences
import bpy.utils.previews
from typing import Optional, cast
from rhubarb_lipsync.rhubarb.rhubarb_command_handling import RhubarbCommandWrapper, RhubarbParser
import pathlib


def addons_path() -> pathlib.Path:
    ap = bpy.utils.user_resource('SCRIPTS', path="addons")
    return pathlib.Path(ap)


def default_executable_path() -> pathlib.Path:
    exe = RhubarbCommandWrapper.executable_default_filename()
    return addons_path() / 'rhubarb_lipsync' / 'bin' / exe


def resources_path() -> pathlib.Path:
    return addons_path() / 'rhubarb_lipsync' / 'resources'


class IconsManager:

    _previews: bpy.utils.previews.ImagePreviewCollection = None
    _loaded: set[str] = set()

    @staticmethod
    def unregister():
        if IconsManager._previews:
            bpy.utils.previews.remove(IconsManager._previews)
            IconsManager._previews = None

    @staticmethod
    def get(key: str):

        if IconsManager._previews is None:
            IconsManager._previews = bpy.utils.previews.new()
        prew = IconsManager._previews
        if not key in IconsManager._loaded:
            IconsManager._loaded.add(key)
            prew.load(key, str(resources_path() / f"{key}.png"), 'IMAGE')
        return prew[key].icon_id


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
            ("pocketSphinx", "pocketSphinx", "PocketSphinx is an open-source speech recognition library that generally gives good results for English"),
            ("phonetic", "phonetic", "This recognizer is language-independent. Use it if your recordings are not in English"),
        ],
        default="pocketSphinx",
    )

    use_extended_shapes: BoolProperty(  # type: ignore
        name="Use extended shapes",
        description="Use three additional mouth shapes G,H,X on top of the six basic",
        default=True,
    )

    default_converted_output_folder: StringProperty(  # type: ignore
        name="Default output for converted files",
        description="Where to put the new wav/ogg files resulted from the conversion from an unsupported formats. Leave blank to use the source file's folder",
        subtype='FILE_PATH',
        default="",
    )

    info_panel_expanded: BoolProperty(default=True)  # type: ignore
    sound_source_panel_expanded: BoolProperty(default=True)  # type: ignore

    def new_command_handler(self):
        return RhubarbCommandWrapper(self.executable_path, self.recognizer, self.use_extended_shapes)

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
        layout.prop(self, "use_extended_shapes")
        layout.prop(self, 'default_converted_output_folder')


class CaptureProperties(PropertyGroup):

    sound: PointerProperty(type=bpy.types.Sound, name="Sound")  # type: ignore
    start_frame: FloatProperty(name="Start frame", default=0)  # type: ignore
    dialog_file: StringProperty(  # type: ignore
        name="Dialog file",
        description="Additional plain-text file with transcription of the sound file to improve accuracy. Works for english only",
        subtype='FILE_PATH',
    )

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
