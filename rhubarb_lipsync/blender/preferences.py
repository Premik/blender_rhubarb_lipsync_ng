import pathlib
from functools import cached_property
from typing import Optional, cast

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, Context, PropertyGroup, Sound, UILayout

import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandWrapper, RhubarbParser


def default_executable_path() -> pathlib.Path:
    exe = RhubarbCommandWrapper.executable_default_filename()
    return ui_utils.addons_path() / 'rhubarb_lipsync' / 'bin' / exe


class CueListPreferences(PropertyGroup):
    highlight_long_cues: FloatProperty(  # type: ignore
        name="Flag long cues time",
        description="If a captured cue is longer that this given time (in second) the cue is drawn in red in the list. Set to -1 to disable.",
        default=0.3,
        soft_min=0.2,
        soft_max=2,
    )
    highlight_short_cues: FloatProperty(  # type: ignore
        name="Flag short cues time",
        description="If a captured cue is shorter that this given time (in second) the cue is drawn in red in the list. Set to -1 to disable.",
        default=0.01,
        soft_min=0.005,
        soft_max=0.3,
    )

    show_col_icon: BoolProperty(default=True, name="Icon")  # type: ignore
    show_col_start_frame: BoolProperty(default=True, name="Start (frames)")  # type: ignore
    show_col_start_time: BoolProperty(default=False, name="Start (time)")  # type: ignore
    show_col_len_frame: BoolProperty(default=False, name="Duration (frames)")  # type: ignore
    show_col_len_time: BoolProperty(default=True, name="Duration (seconds)")  # type: ignore
    show_col_play: BoolProperty(default=True, name="Play button")  # type: ignore

    as_grid: BoolProperty(default=False, name="As gird", description="Display the list in the grid mode")  # type: ignore
    sync_on_select: BoolProperty(  # type: ignore
        default=True,
        name="Sync time on select",
        description="Synchronize the timeline with the cue start time when the item is selected",
    )

    @property
    def timecols(self) -> list[bool]:
        return [
            self.show_col_start_frame,
            self.show_col_start_time,
            self.show_col_len_frame,
            self.show_col_len_time,
        ]

    def visible_timecols_count(self) -> int:
        return self.timecols.count(True)

    @cached_property
    def props_names(self) -> list[str]:
        return [k for k in self.__annotations__]

    @cached_property
    def col_props_names(self) -> list[str]:
        return [k for k in self.props_names if 'show_col' in k]

    @cached_property
    def noncol_props_names(self) -> list[str]:
        return [k for k in self.props_names if not 'show_col' in k]


class RhubarbAddonPreferences(AddonPreferences):
    bl_idname = 'rhubarb_lipsync'

    @staticmethod
    def from_context(ctx: Context, require=True) -> 'RhubarbAddonPreferences':
        blid = RhubarbAddonPreferences.bl_idname
        if not blid in ctx.preferences.addons:
            if require:  # There is no inbuilt Illegal state or similar exception in python
                raise RuntimeError(f"The '{blid}' addon preferences not found in the context.")
            return None  # type: ignore
        addon = ctx.preferences.addons[blid]
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
        name="Converted files output",
        description="Where to put the new wav/ogg files resulted from the conversion from an unsupported formats. Leave blank to use the source file's folder",
        subtype='FILE_PATH',
        default="",
    )

    always_show_conver: BoolProperty(  # type: ignore
        name="Always show the convert buttons",
        description="Always show the convert buttons in the panel. Even when the conversion is likely not needed.",
        default=False,
    )

    log_level: IntProperty(default=0)  # type: ignore
    info_panel_expanded: BoolProperty(default=False)  # type: ignore
    sound_source_panel_expanded: BoolProperty(default=True)  # type: ignore
    caputre_panel_expanded: BoolProperty(default=True)  # type: ignore

    cue_list_prefs: PointerProperty(type=CueListPreferences, name="Cues list preferences")  # type: ignore

    def new_command_handler(self) -> RhubarbCommandWrapper:
        return RhubarbCommandWrapper(self.executable_path, self.recognizer, self.use_extended_shapes)

    def draw(self, context: Context) -> None:
        layout: UILayout = self.layout

        layout.prop(self, "executable_path_string")
        row = layout.row().split(factor=0.243)
        # split = layout.row(heading="Label")
        row.label(text="Rhubarb executable version:")

        # Hack to avoid circumvent circular imports
        import rhubarb_lipsync.blender.rhubarb_operators as rhubarb_operators

        ver = rhubarb_operators.GetRhubarbExecutableVersion.get_cached_value(context)

        if ver:  # Cached value, just show
            row.label(text=ver)
        else:  # Not cached, offer button
            row.operator(rhubarb_operators.GetRhubarbExecutableVersion.bl_idname)

        # row = layout.row()
        # row.prop(self, "recognizer")
        # split = layout.row().split(factor=0.5)
        layout.prop(self, "recognizer")

        layout.prop(self, "use_extended_shapes")
        # layout.prop(self.cue_list_prefs, "highlight_long_cues")
        # layout.prop(self.cue_list_prefs, "highlight_short_cues")

        layout.separator()
        layout.prop(self, 'default_converted_output_folder')
        layout.prop(self, 'always_show_conver')

        from rhubarb_lipsync.blender.misc_operators import SetLogLevel
        from rhubarb_lipsync.rhubarb.log_manager import logManager

        row = layout.row().split(factor=0.243)
        row.label(text=f"Log level ({logManager.current_level_name})")
        row.operator_menu_enum(SetLogLevel.bl_idname, 'level')
