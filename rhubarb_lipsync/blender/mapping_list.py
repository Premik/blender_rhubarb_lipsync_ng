from bpy.types import Context, UILayout, UIList, Panel, UI_UL_list


import rhubarb_lipsync.blender.mapping_operators as mapping_operators
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences, MappingPreferences
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, MappingItem


def draw_mapping_item(ctx: Context, layout: UILayout, mp: MappingProperties, itemIndex: int) -> None:
    prefs = RhubarbAddonPreferences.from_context(ctx)
    mlp: MappingPreferences = prefs.mapping_prefs
    clp: CueListPreferences = prefs.cue_list_prefs
    item: MappingItem = mp.items[itemIndex]

    split = layout.split(factor=0.1)
    # row = split.row()
    col1 = split.column().row()
    col2 = split.column().row(align=True)

    # row.template_icon(icon_value=IconsManager.cue_image(item.key), scale=5)
    # row = split.row()

    if not prefs.use_extended_shapes and item.cue_info.extended:
        col1.enabled = False  # Indicate extended shape not in use
    if clp.as_circle:
        key_label = item.cue_info.key_displ
    else:
        key_label = item.key
    col1.operator(mapping_operators.ShowCueInfoHelp.bl_idname, text=key_label).key = item.key
    desc = f"{item.action_str}"

    col2.operator(mapping_operators.ListFilteredActions.bl_idname, text=desc, icon="DOWNARROW_HLT").target_cue_index = itemIndex

    # col2.prop(item, "frame_start", text="")
    # col2.prop(item, "frame_count", text="")
    # col2.prop(item, "key", text="")

    col2.operator(mapping_operators.SetActionFrameRange.bl_idname, text="", icon="ARROW_LEFTRIGHT").target_cue_index = itemIndex
    # col2.popover(panel=FrameRangeSelectionPanel.bl_idname, text="", icon="ARROW_LEFTRIGHT")
    col2.operator(mapping_operators.ClearMappedActions.bl_idname, text="", icon="TRASH").target_cue_index = itemIndex


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


class FrameRangeSelectionPanel(Panel):
    bl_idname = "RLPS_PT_frame_range_selection"
    bl_label = "Frame Range Selection"
    bl_space_type = "PROPERTIES"
    bl_region_type = "HEADER"

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        clp: CueListPreferences = prefs.cue_list_prefs
        mlp: MappingPreferences = prefs.mapping_prefs
        mprops: MappingProperties = MappingProperties.from_context(context)
        layout = self.layout

        layout.prop(clp, "as_circle")
        layout.separator()
        layout.label(text=f"{mprops.index}")
