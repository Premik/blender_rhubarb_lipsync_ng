from functools import cached_property
from typing import Any

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, CollectionProperty, Context, PropertyGroup, UILayout, UIList

from rhubarb_lipsync.blender.misc_operators import PlayRange
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.blender.properties import MouthCueList, MouthCueListItem
from rhubarb_lipsync.blender.ui_utils import IconsManager
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue


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
        prefs = RhubarbAddonPreferences.from_context(context)
        split = layout.split(factor=0.2)

        # row.scale_x = 1.15
        # row.scale_x = 0.95

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = split.row()  # Icon and shape key (0.2)

            row.label(icon_value=IconsManager.cue_image(item.cue.key))
            row.label(text=item.key)
            row = split.row()  # Times and operators (0.8)
            subs = row.split(factor=0.85)

            row = subs.row()  # Times (0.85)
            # row.active = False
            # row.enabled = False
            # row.
            if item.cue.key == 'X':
                row.active = False
            else:
                long = prefs.highlight_long_cues
                short = prefs.highlight_short_cues
                if (long > 0 and item.duration > long) or (short >= 0 and item.duration <= short):
                    row.alert = True  # Too long/short cue is suspisous, unless it is silence

            row.label(text=f"{item.frame_str(context)}")
            row.label(text=f"{item.time_str}s")
            row.label(text=f"{item.duration_str}s")

            row = subs.row()  # Operator (0.15)
            op = row.operator(PlayRange.bl_idname, text="", icon="TRIA_RIGHT_BAR")

            op.start_frame = int(item.frame_float(context))
            op.play_frames = item.duration_frames(context)

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
