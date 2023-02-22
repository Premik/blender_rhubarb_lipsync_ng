from functools import cached_property
from typing import Any

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, CollectionProperty, Context, PropertyGroup, UILayout, UIList

from rhubarb_lipsync.blender.misc_operators import PlayRange
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences, CueListPreferences
from rhubarb_lipsync.blender.properties import MappingList, MappingListItem
from rhubarb_lipsync.blender.ui_utils import IconsManager
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue


class MappingUIList(UIList):
    bl_idname = "RLPS_UL_mapping"

    def draw_item(
        self,
        context: Context,
        layout: UILayout,
        data: MappingList,
        item: MappingListItem,
        icon: int,
        active_data: MappingList,
        active_property: str,
        index: int,
        flt_flag: int,
    ) -> None:
        layout.prop(item, 'key')
