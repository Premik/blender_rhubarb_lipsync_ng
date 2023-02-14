from functools import cached_property
from typing import Any

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, CollectionProperty, Context, PropertyGroup, UILayout, UIList

from rhubarb_lipsync.blender.misc_operators import PlayRange
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences, CueListPreferences
from rhubarb_lipsync.blender.properties import MouthCueList, MouthCueListItem
from rhubarb_lipsync.blender.ui_utils import IconsManager
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue


class MouthCueUIList(UIList):

    bl_idname = "RLPS_UL_cues"

    def cuelist_prefs(self, ctx: Context) -> CueListPreferences:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        return prefs.cue_list_prefs

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
            self.draw_grid(layout, item)

    def draw_compact(self, layout: UILayout, item: MouthCueListItem, context: Context) -> None:
        clp = self.cuelist_prefs(context)
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
            row.label(text=f"{item.time_str}s")
        if clp.show_col_len_frame:
            row.label(text=f"{item.duration_frames(context)}")
        if clp.show_col_len_time:
            row.label(text=f"{item.duration_str}s")

        if clp.show_col_play:
            row = subs.row()  # Operator (0.15)
            op = row.operator(PlayRange.bl_idname, text="", icon="TRIA_RIGHT_BAR")
            op.start_frame = int(item.frame_float(context))
            op.play_frames = item.duration_frames(context)

    def draw_grid(self, layout: UILayout, item: MouthCueListItem) -> None:
        layout.alignment = 'CENTER'

        # l.emboss = 'NONE'
        # layout.alignment = 'EXPAND'
        # l = layout.row()
        # l.scale_x = 1
        # l.alignment = 'CENTER'

        layout.label(text=item.key)
