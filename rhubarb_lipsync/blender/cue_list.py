from functools import cached_property
from typing import Any

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, CollectionProperty, Context, PropertyGroup, UILayout, UIList
from bpy.types import UI_UL_list

from rhubarb_lipsync.blender.sound_operators import PlayRange
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences, CueListPreferences
from rhubarb_lipsync.blender.capture_properties import MouthCueList, MouthCueListItem, CaptureListProperties
from rhubarb_lipsync.blender.ui_utils import IconsManager
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue


class MouthCueUIList(UIList):
    bl_idname = "RLPS_UL_cues"

    def cuelist_prefs(self, ctx: Context) -> CueListPreferences:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        return prefs.cue_list_prefs

    def filter_items(self, context: Context, data: MouthCueList, propname: str):
        f = self.filter_name.upper()
        filtered = UI_UL_list.filter_items_by_name(f, self.bitflag_filter_item, data.items, "key", reverse=False)
        return filtered, []

    def draw_item(
        self,
        context: Context,
        layout: UILayout,
        data: MouthCueList,
        item: MouthCueListItem,
        icon: int,
        active_data: MouthCueList,
        active_property: str,
        index: int,
        flt_flag: int,
    ) -> None:
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            self.draw_compact(layout, item, context)
        elif self.layout_type in {'GRID'}:
            self.draw_grid(layout, item, context)

    def draw_compact(self, layout: UILayout, item: MouthCueListItem, context: Context) -> None:
        clp = self.cuelist_prefs(context)
        props = CaptureListProperties.capture_from_context(context)
        # row = layout.row()
        # prefs = RhubarbAddonPreferences.from_context(context)
        if clp.show_col_icon:
            split = layout.split(factor=0.2)
        else:
            split = layout.split(factor=0.1)

        # row.scale_x = 1.15
        # row.scale_x = 0.95

        row = split.row()  # Icon(0.1) and shape key (0.1)

        if clp.show_col_icon:
            row.label(icon_value=IconsManager.cue_image(item.cue.key))
        if clp.as_circle:
            row.label(text=item.cue.info.key_displ)
        else:
            row.label(text=item.key)

        row = split.row()  # Times and operators (0.8)
        if clp.show_col_play:
            subs = row.split(factor=0.85)
        else:
            subs = row

        row = subs.row()  # Times (0.85)
        # row.active = False
        # row.enabled = False
        # row.
        if item.cue.key == 'X':
            row.active = False
        else:
            long = clp.highlight_long_cues
            short = clp.highlight_short_cues
            if (long > 0 and item.duration > long) or (short >= 0 and item.duration <= short):
                row.alert = True  # Too long/short cue is suspisous, unless it is silence

        if clp.show_col_start_frame:
            row.label(text=f"{item.frame_str(context)}")
        if clp.show_col_start_time:
            row.label(text=f"{item.time_str(context)}s")
        if clp.show_col_len_frame:
            row.label(text=f"{item.duration_frames(context)}")
        if clp.show_col_len_time:
            row.label(text=f"{item.duration_str}s")

        if clp.show_col_play:
            row = subs.row()  # Operator (0.15)
            op = row.operator(PlayRange.bl_idname, text="", icon="TRIA_RIGHT_BAR")

            op.start_frame = int(item.frame_float(context))
            op.play_frames = item.duration_frames(context)

    def draw_grid(self, layout: UILayout, item: MouthCueListItem, context: Context) -> None:
        layout.alignment = 'CENTER'

        # l.emboss = 'NONE'
        # layout.alignment = 'EXPAND'
        # l = layout.row()
        # l.scale_x = 1
        # l.alignment = 'CENTER'
        if self.cuelist_prefs(context).as_circle:
            layout.label(text=item.cue.info.key_displ)
        else:
            layout.label(text=item.key)
