from functools import cached_property

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, Context, PropertyGroup, UIList, UILayout, CollectionProperty

from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue
from rhubarb_lipsync.blender.properties import MouthCueListItem, MouthCueList
from rhubarb_lipsync.blender.misc_operators import PlayAndStop
from typing import Any


class MouthCueUIList(UIList):

    bl_idname = "RLPS_UL_cues"

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

        # row = layout.row()
        split = layout.split(factor=0.2)

        # row.scale_x = 1.15
        # row.scale_x = 0.95

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = split.row()
            row.label(icon="DOT")
            row.label(text=item.key)
            row = split.row()
            row.label(text=f"{item.frame_str(context)}")
            row.label(text=f"{item.time_str}s")
            op = row.operator(PlayAndStop.bl_idname, text="", icon="TRIA_RIGHT_BAR")
            op.start_frame = item.frame_float(context)
            op.play_frames = int(round(item.end_frame_float(context) - item.frame_float(context)))

            # row.prop(item, 'start')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            l = layout
            # l.emboss = 'NONE'
            # layout.alignment = 'EXPAND'
            # l = layout.row()
            # l.scale_x = 1
            # l.alignment = 'CENTER'

            l.label(text=item.key)
