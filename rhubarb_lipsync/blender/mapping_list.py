
from bpy.types import Context, SpaceDopeSheetEditor, UILayout, UIList
from bpy.types import UI_UL_list, Panel

import rhubarb_lipsync.blender.mapping_operators as mapping_operators
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences, MappingPreferences
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, MappingItem
from rhubarb_lipsync.blender.ui_utils import IconsManager


class TestPanel(Panel):
    bl_idname = "RLPS_PT_TestPanel"
    bl_label = "Test"
    bl_parent_id = "RLPS_PT_map_and_bake"                    
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
   # bl_category = "RLSP"
    

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)

        layout = self.layout
        row = layout.row()
        row.label(text="TEST1")

class TestPanel2(Panel):
    bl_idname = "RLPS_PT_TestPanel2"
    bl_label = "Test"   
    bl_parent_id = "RLPS_PT_map_and_bake"   
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RLSP"
    

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)

        layout = self.layout
        row = layout.row()
        row.label(text="TEST2")

def draw_mapping_item(ctx: Context, layout: UILayout, mp:MappingProperties, itemIndex:int):
    prefs = RhubarbAddonPreferences.from_context(ctx)
    mlp: MappingPreferences = prefs.mapping_prefs
    clp: CueListPreferences = prefs.cue_list_prefs
    item = mp.items[itemIndex]

    split = layout.split(factor=0.1)
    #row = split.row()
    row=split    
    #row.template_icon(icon_value=IconsManager.cue_image(item.key), scale=5)
    # row = split.row()

    
    if not prefs.use_extended_shapes and item.cue_desc.extended:
        row.enabled = False  # Indicate extended shape not in use
    if clp.as_circle:
        row.label(text=item.cue_desc.key_displ)
    else:
        row.label(text=item.key)

    
    #row = split.row()
    row = split.row()
    if mp.nla_map_action:
        row.prop(item, 'action', text="")
        
        #row.template_ID(item, "action")
        #row.template_ID_preview(item, "action")
        #row.template_any_ID(item, "action")
        

    # TODO: Doesn't work
    if mlp.actions_multiline_view:
        row = layout.row()
    if mp.nla_map_shapekey:
        row.prop(item, 'shapekey_action', text="")

    
    # row.template_ID(item, "action", new="action.new", unlink="action.unlink")

    

    if mlp.show_help_button:
        row.operator(mapping_operators.ShowCueInfoHelp.bl_idname, icon="QUESTION", text="").key = item.key


def draw_mapping_item_multiline(ctx: Context, layout: UILayout, mp:MappingProperties, itemIndex:int):
    prefs = RhubarbAddonPreferences.from_context(ctx)
    mlp: MappingPreferences = prefs.mapping_prefs
    clp: CueListPreferences = prefs.cue_list_prefs
    item = mp.items[itemIndex]

    layout = layout.box().column(align=True)
    split = layout.split(factor=0.1)
    c1 = split.column()
    c2 = split.column()

    c1.label(text="c1")
    c1.label(text="c1")
    c2.label(text="c2")
    c1.label(text="c1")
    c2.label(text="c2")
    c2.label(text="c2")
    c2.label(text="c2")

    return
    
    row = split.row()
    #row = split
    
    
    #row.template_icon(icon_value=IconsManager.cue_image(item.key), scale=5)
    # row = split.row()

    
    if not prefs.use_extended_shapes and item.cue_desc.extended:
        row.enabled = False  # Indicate extended shape not in use
    
    if clp.as_circle:
        row.label(text=item.cue_desc.key_displ)
    else:
        row.label(text=item.key)


    row = split.row()
    if mp.nla_map_action:
        row.prop(item, 'action', text="")
        
        #row.template_ID(item, "action")
        #row.template_ID_preview(item, "action")
        #row.template_any_ID(item, "action")
        

    
    row = split.row()
    row.label(text=item.key)
    #if mp.nla_map_shapekey:
    row.prop(item, 'shapekey_action', text="")
    # row.template_ID(item, "action", new="action.new", unlink="action.unlink")

    

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
        prefs = RhubarbAddonPreferences.from_context(context)
        mlp: MappingPreferences = prefs.mapping_prefs
        clp: CueListPreferences = prefs.cue_list_prefs
        draw_mapping_item(context, layout, data, index)
        #draw_mapping_item_multiline(context, layout, data, index)

        

