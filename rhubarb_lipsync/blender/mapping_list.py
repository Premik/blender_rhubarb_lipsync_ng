from bpy.types import Context, UILayout, UIList
from bpy.types import UI_UL_list

import rhubarb_lipsync.blender.mapping_operators as mapping_operators
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences, MappingPreferences
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, MappingItem


def draw_mapping_item(ctx: Context, layout: UILayout, mp: MappingProperties, itemIndex: int):
    prefs = RhubarbAddonPreferences.from_context(ctx)
    mlp: MappingPreferences = prefs.mapping_prefs
    clp: CueListPreferences = prefs.cue_list_prefs
    item = mp.items[itemIndex]

    split = layout.split(factor=0.1)
    # row = split.row()
    row = split
    # row.template_icon(icon_value=IconsManager.cue_image(item.key), scale=5)
    # row = split.row()

    if not prefs.use_extended_shapes and item.cue_desc.extended:
        row.enabled = False  # Indicate extended shape not in use
    if clp.as_circle:
        row.label(text=item.cue_desc.key_displ)
    else:
        row.label(text=item.key)

    row = split.row()
    row.operator(mapping_operators.ListFilteredActions.bl_idname, text=str(item.name))

    if mlp.show_help_button:
        row.operator(mapping_operators.ShowCueInfoHelp.bl_idname, icon="QUESTION", text="").key = item.key


class MappingUIList(UIList):
    bl_idname = "RLPS_UL_mapping"

    def filter_items(self, context: Context, data: MappingProperties, propname: str):
        f = self.filter_name.upper()
        filtered = UI_UL_list.filter_items_by_name(f, self.bitflag_filter_item, data.items, "key", reverse=False)
        return filtered, []

    def draw_item(
        self,
        context: Context,
        layout: UILayout,
        data: MappingProperties,
        item: MappingItem,
        icon: int,
        active_data: MappingProperties,
        active_property: str,
        index: int,
        flt_flag: int,
    ) -> None:
        RhubarbAddonPreferences.from_context(context)
        draw_mapping_item(context, layout, data, index)
        # draw_mapping_item_multiline(context, layout, data, index)
