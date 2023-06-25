import pathlib
from functools import cached_property
from typing import Optional, cast

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, Context, PropertyGroup, Sound, UILayout, Object
from typing import Any, Callable, Optional, cast, Generator, Iterator
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandWrapper, RhubarbParser


def default_executable_path() -> pathlib.Path:
    """Path where the rhubarb executable is expected by default. When the addon is installed"""
    exe = RhubarbCommandWrapper.executable_default_filename()
    return ui_utils.addons_path() / 'rhubarb_lipsync' / 'bin' / exe


def local_executable_path(verify=True) -> pathlib.Path:
    """Rhubarb executable path relative to this source file. Should work even when the plugin is not installed."""
    bin_path = pathlib.Path(__file__).parent.parent / "bin"
    exe = bin_path / RhubarbCommandWrapper.executable_default_filename()
    if verify:
        assert bin_path.exists(), f"{bin_path} doesn't exists"
        assert bin_path.is_dir(), f"{bin_path} is not a directory"
        assert exe.exists(), f"{exe} doesn't exists"
    return exe


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

    show_col_icon: BoolProperty(default=False, name="Icon")  # type: ignore
    show_col_start_frame: BoolProperty(default=True, name="Start (frames)")  # type: ignore
    show_col_start_time: BoolProperty(default=False, name="Start (time)")  # type: ignore
    show_col_len_frame: BoolProperty(default=False, name="Duration (frames)")  # type: ignore
    show_col_len_time: BoolProperty(default=True, name="Duration (seconds)")  # type: ignore
    show_col_play: BoolProperty(default=True, name="Play button")  # type: ignore

    as_grid: BoolProperty(default=False, name="As gird", description="Display the list in the grid mode")  # type: ignore
    as_circle: BoolProperty(default=True, name="Cue key circle font", description="Show the cue keys A,B,C as Ⓐ,Ⓑ,Ⓒ")  # type: ignore
    sync_on_select: BoolProperty(  # type: ignore
        default=True,
        name="Sync time on select",
        description="Synchronize the timeline with the cue start time when the item is selected",
    )
    preview: BoolProperty(  # type: ignore
        default=True,
        name="Preview on playback",
        description="Animate the icon in the panel while in playback.",
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


class MappingPreferences(PropertyGroup):
    actions_multiline_view: BoolProperty(  # type: ignore
        name="Show actions on two lines",
        description="When both regular action and shape-key action are visible show them on two lines instead of side-by-side.",
        default=False,
    )

    show_help_button: BoolProperty(  # type: ignore
        name="Show help button",
        description="For each cue-type show the question-mark button with a help popup.",
        default=True,
    )

    object_selection_type: EnumProperty(  # type: ignore
        name="Objects to bake",
        items=[
            ("Active", "Active", "Bake only the active object"),
            ("Selected", "Selected", "Bake all the selected objects which has a mapping"),
            ("All", "All", "Bake all the objects of the current scene which has a mapping"),
        ],
        default="All",
    )

    def object_selection(self, ctx: Context) -> Iterator[Object]:
        if self.object_selection_type == 'Active':
            return iter([ctx.active_object])
        if self.object_selection_type == 'Selected':
            return ctx.selected_objects
        if self.object_selection_type == 'All':
            return ctx.scene.objects
        raise AttributeError(f"Unknown object_selection_type {self.bake_object_selection}")


class RhubarbAddonPreferences(AddonPreferences):
    bl_idname = 'rhubarb_lipsync'

    @staticmethod
    def from_context(ctx: Context, require=True) -> Optional['RhubarbAddonPreferences']:
        blid = RhubarbAddonPreferences.bl_idname
        if not blid in ctx.preferences.addons:
            if require:  # There is no inbuilt Illegal state or similar exception in python
                raise RuntimeError(f"The '{blid}' addon preferences not found in the context.")
            return None
        addon = ctx.preferences.addons[blid]
        return cast(RhubarbAddonPreferences, addon.preferences)

    executable_path_string: StringProperty(  # type: ignore
        name="Rhubarb lipsync executable",
        subtype='FILE_PATH',
        default=str(default_executable_path()),
    )

    @property
    def executable_path(self) -> pathlib.Path | None:
        if not self.executable_path_string:
            return None
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
        name="Use extended shapes ",
        description="Use three additional mouth shapes ⒼⒽⓍ on top of the six basic",
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

    sound_mem_cache_default: BoolProperty(  # type: ignore
        name="Cache sound by default",
        description="Cache the newly created sound in memory by default. Enabling cache greatly improves the sound playback synchronization precision. Especially noticable for ogg files.",
        default=True,
    )

    log_level: IntProperty(default=0)  # type: ignore
    info_panel_expanded: BoolProperty(default=False)  # type: ignore
    sound_source_panel_expanded: BoolProperty(default=True)  # type: ignore
    caputre_panel_expanded: BoolProperty(default=True)  # type: ignore
    strip_timing_setting_panel_expanded: BoolProperty(default=True)  # type: ignore
    mapping_list_panel_expanded: BoolProperty(default=True)  # type: ignore
    bake_info_panel_expanded: BoolProperty(default=True)  # type: ignore
    bake_errors_panel_expanded: BoolProperty(default=True)  # type: ignore

    cue_list_prefs: PointerProperty(type=CueListPreferences, name="Cues list preferences")  # type: ignore
    mapping_prefs: PointerProperty(type=MappingPreferences, name="Mapping list preferences")  # type: ignore

    def new_command_handler(self) -> RhubarbCommandWrapper:
        return RhubarbCommandWrapper(self.executable_path, self.recognizer, self.use_extended_shapes)

    def draw(self, context: Context) -> None:
        layout: UILayout = self.layout

        layout.prop(self, "executable_path_string")
        row = layout.row().split(factor=0.243)
        # split = layout.row(heading="Label")
        row.label(text="Rhubarb executable version:")

        # Hack to circumvent circular imports
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
        layout.prop(self, 'sound_mem_cache_default')

        from rhubarb_lipsync.blender.misc_operators import SetLogLevel
        from rhubarb_lipsync.rhubarb.log_manager import logManager

        row = layout.row().split(factor=0.243)
        row.label(text=f"Log level ({logManager.current_level_name})")
        row.operator_menu_enum(SetLogLevel.bl_idname, 'level')
