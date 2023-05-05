from functools import cached_property
from typing import Any

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, CollectionProperty, Context, PropertyGroup, UILayout, UIList

import rhubarb_lipsync.blender.mapping_operators as mapping_operators
from rhubarb_lipsync.blender.sound_operators import PlayRange
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, MappingListItem
from rhubarb_lipsync.blender.ui_utils import IconsManager

from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfos, MouthShapeInfo


class MappingUIList(UIList):
    bl_idname = "RLPS_UL_mapping"

    def draw_item(
        self,
        context: Context,
        layout: UILayout,
        data: MappingProperties,
        item: MappingListItem,
        icon: int,
        active_data: MappingProperties,
        active_property: str,
        index: int,
        flt_flag: int,
    ) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        clp: CueListPreferences = prefs.cue_list_prefs

        split = layout.split(factor=0.1)
        row = split.row()
        # row.template_icon(icon_value=IconsManager.cue_image(item.key), scale=5)
        # row = split.row()

        if not prefs.use_extended_shapes and item.cue_desc.extended:
            row.enabled = False  # Indicate extended shape not in use
        if clp.as_circle:
            row.label(text=item.cue_desc.key_displ)
        else:
            row.label(text=item.key)
        row = split.row()
        row.prop(item, 'action', text="")
        # row.template_ID(item, "action", new="action.new", unlink="action.unlink")
        row.operator(mapping_operators.ShowCueInfoHelp.bl_idname, icon="QUESTION", text="").key = item.key

        # return wm.invoke_search_popup(self)
