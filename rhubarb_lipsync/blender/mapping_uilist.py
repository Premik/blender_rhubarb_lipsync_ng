from bpy.types import Context, UI_UL_list, UILayout, UIList

import rhubarb_lipsync.blender.mapping_operators as mapping_operators
from rhubarb_lipsync.blender import mapping_utils
from rhubarb_lipsync.blender.mapping_properties import MappingItem, MappingProperties
from rhubarb_lipsync.blender.preferences import CueListPreferences, MappingPreferences, RhubarbAddonPreferences


def draw_mapping_item(ctx: Context, layout: UILayout, mp: MappingProperties, itemIndex: int) -> None:
    prefs = RhubarbAddonPreferences.from_context(ctx)
    mlp: MappingPreferences = prefs.mapping_prefs
    clp: CueListPreferences = prefs.cue_list_prefs
    mi: MappingItem = mp.items[itemIndex]

    split = layout.split(factor=0.1)
    # row = split.row()
    col1 = split.column().row()
    col2 = split.column().row(align=True)

    # row.template_icon(icon_value=IconsManager.cue_icon(item.key), scale=5)
    # row = split.row()

    emboss = mlp.action_buttons_emboss
    if not prefs.use_extended_shapes and mi.cue_info.extended:
        col1.enabled = False  # Indicate extended shape not in use
    if clp.as_circle:
        key_label = mi.cue_info.key_displ
    else:
        key_label = mi.key
    col1.operator(mapping_operators.ShowCueInfoHelp.bl_idname, emboss=emboss, text=key_label).key = mi.key
    if mi.custom_frame_ranage:
        desc = f"{mi.action_str} {mi.frame_range_str}"
    else:
        desc = f"{mi.action_str}"

    blid = mapping_operators.ListFilteredActions.bl_idname
    col2.operator(blid, text=desc, emboss=mlp.action_dropdown_emboss, icon="DOWNARROW_HLT").target_cue_index = itemIndex

    # col2.prop(item, "frame_start", text="")
    # col2.prop(item, "frame_count", text="")
    # col2.prop(item, "key", text="")

    if mapping_utils.is_mapping_item_active(ctx, mi, ctx.object):
        icon = "SNAP_FACE"
    else:
        icon = "PLAY"

    blid = mapping_operators.PreviewMappingAction.bl_idname
    col2.operator(blid, text="", emboss=emboss, icon=icon).target_cue_index = itemIndex

    if mi.custom_frame_ranage:
        icon = "CENTER_ONLY"
    else:
        icon = "ARROW_LEFTRIGHT"
    blid = mapping_operators.SetActionFrameRange.bl_idname
    col2.operator(blid, text="", emboss=emboss, icon=icon).target_cue_index = itemIndex

    blid = mapping_operators.ClearMappedActions.bl_idname
    col2.operator(blid, text="", emboss=emboss, icon="TRASH").target_cue_index = itemIndex


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
