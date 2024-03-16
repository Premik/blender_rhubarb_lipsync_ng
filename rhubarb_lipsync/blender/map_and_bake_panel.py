import logging

import bpy
from bpy.types import Context

import rhubarb_lipsync.blender.baking_operators as baking_operators
import rhubarb_lipsync.blender.mapping_operators as mapping_operators
import rhubarb_lipsync.blender.ui_utils as ui_utils
import rhubarb_lipsync.blender.mapping_list as mapping_list
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences, MappingPreferences
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, ResultLogListProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, NlaTrackRef, StripPlacementProperties
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthShapeInfos
from rhubarb_lipsync.blender.misc_operators import ShowResultLogDetails
import rhubarb_lipsync.blender.mapping_utils as mapping_utils

log = logging.getLogger(__name__)


def draw_action_filters(layout: bpy.types.UILayout, mprops: MappingProperties, icons_only: bool):
    text = "" if icons_only else None
    if mprops.only_shapekeys:
        layout.prop(mprops, "only_shapekeys", text=text, icon="SHAPEKEY_DATA")
    else:
        layout.prop(mprops, "only_shapekeys", text=text, icon="OBJECT_DATAMODE")
    layout.prop(mprops, "only_valid_actions", text=text, icon="ERROR")
    layout.prop(mprops, "only_asset_actions", text=text, icon="ASSET_MANAGER")


class MappingListOptionsPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_mapping_list_options"
    bl_label = "Mapping list display options"
    bl_space_type = "PROPERTIES"
    bl_region_type = "HEADER"

    # bl_category = "RLSP"

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        clp: CueListPreferences = prefs.cue_list_prefs
        mlp: MappingPreferences = prefs.mapping_prefs
        mprops: MappingProperties = MappingProperties.from_context(context)
        layout = self.layout
        layout.label(text=MappingListOptionsPanel.bl_label)
        # layout.prop(mlp, "show_help_button")
        layout.prop(clp, "as_circle")
        layout.prop(mlp, "action_buttons_emboss")
        layout.separator()
        layout.label(text="Action filters")
        draw_action_filters(layout, mprops, False)
        # layout.prop(mlp, "actions_multiline_view")


class MappingAndBakingPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_map_and_bake"
    bl_label = "RLPS: Cue mapping and baking"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RLSP"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 1

    def draw_config(self) -> None:
        mprops: MappingProperties = MappingProperties.from_context(self.ctx)
        row = self.layout.row()

        filtersRow = row.row(align=True)
        draw_action_filters(filtersRow, mprops, True)

        actionRow = row.row(align=True)
        actionRow.label(text="")  # Spacer to force icons alight to the right
        actionRow.popover(panel=MappingListOptionsPanel.bl_idname, text="", icon="VIS_SEL_11")

    def draw_mapping_list(self) -> bool:
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        mprops: MappingProperties = MappingProperties.from_context(self.ctx)
        if not ui_utils.draw_expandable_header(prefs, "mapping_list_panel_expanded", "Mapping", self.layout):
            return False
        self.draw_config()

        layout = self.layout

        layout.row(align=True)
        layout.template_list(mapping_list.MappingUIList.bl_idname, "Mapping", mprops, "items", mprops, "index")
        # i=mprops.index
        # mapping_list.draw_mapping_item_multiline(self.ctx, layout, mprops, i)
        return True

    def draw_nla_track_picker(self, ctx: Context, track_field_name: str, text: str) -> None:
        row = self.layout.row(align=True)
        mprops: MappingProperties = MappingProperties.from_context(self.ctx)
        track: NlaTrackRef = getattr(mprops, track_field_name)
        # row.use_property_split = False
        row.prop(track, 'name', text=text)
        # row.prop(track, 'index')
        op: mapping_operators.CreateNLATrack = row.operator(mapping_operators.CreateNLATrack.bl_idname, text="", icon="DUPLICATE")
        # obj_name = self.ctx.object and self.ctx.object.name or ''
        # op.name = f"RLPS {obj_name} {text}" # Include object name
        if mapping_utils.does_object_support_shapekey_actions(ctx.object):
            op.name = f"RLPS Key {text}"
        else:
            op.name = f"RLPS {text}"
        op.track_field_name = track_field_name
        # op.trackRef=track

        # row.operator(capture_operators.DeleteCaptureProps.bl_idname, text="", icon="PANEL_CLOSE")

    def draw_nla_setup(self) -> None:
        self.draw_nla_track_picker(self.ctx, "nla_track1", "Track 1")
        self.draw_nla_track_picker(self.ctx, "nla_track2", "Track 2")

    def draw_strip_placement_settings(self) -> None:
        mprops: MappingProperties = MappingProperties.from_context(self.ctx)
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        row = self.layout.row(align=True)
        strip_placement: StripPlacementProperties = mprops.strip_placement
        if not ui_utils.draw_expandable_header(prefs, "strip_placement_setting_panel_expanded", "Strip placement settings", row):
            return
        sideRow = row.row(align=True)
        sideRow.label(text="")  # Spacer to force icons alight to the right
        sideRow.operator(baking_operators.ShowPlacementHelp.bl_idname, text="", icon="QUESTION")
        # sideRow.operator(capture_operators.DeleteCaptureProps.bl_idname, text="", icon="PANEL_CLOSE")

        self.layout.use_property_decorate = False
        row = self.layout.row(align=True)
        row.prop(strip_placement, 'scale_min', text="Scale Min")
        row.prop(strip_placement, 'scale_max', text="Max")
        id = baking_operators.PlacementScaleFromPreset.bl_idname
        row.operator_menu_enum(id, "scale_type", text="", icon="DOWNARROW_HLT")

        row = self.layout.row(align=True)
        row.prop(strip_placement, 'offset_start', text="Offset Start")
        row.prop(strip_placement, 'offset_end', text="End")
        id = baking_operators.PlacementOffsetFromPreset.bl_idname
        row.operator_menu_enum(id, "offset_type", text="", icon="DOWNARROW_HLT")

        col = self.layout.column(align=False)
        col.use_property_split = True
        col.prop(strip_placement, 'extrapolation')
        col.prop(strip_placement, 'blend_type')

        row = self.layout.row(align=True)
        if strip_placement.use_auto_blend:
            row.enabled = False

        row.prop(strip_placement, 'blend_in', text="Blend In")
        row.prop(strip_placement, 'blend_out', text="Out")
        id = baking_operators.PlacementBlendInOutFromOverlap.bl_idname
        row.operator_menu_enum(id, "sync_type", text="", icon="DOWNARROW_HLT")

        self.layout.prop(strip_placement, 'use_auto_blend')

    def draw(self, context: Context) -> None:
        try:
            self.ctx = context
            layout = self.layout

            selection_error = MappingProperties.context_selection_validation(context)
            if selection_error:
                ui_utils.draw_error(self.layout, selection_error)
                return
            mprops: MappingProperties = MappingProperties.from_context(context)
            if len(mprops.items) != len(MouthShapeInfos.all()):
                layout.alert = True
                layout.operator(mapping_operators.BuildCueInfoUIList.bl_idname)
                return

            if self.draw_mapping_list():
                self.draw_nla_setup()
            self.draw_strip_placement_settings()

            layout.operator(baking_operators.BakeToNLA.bl_idname, icon="NLA")
            rll: ResultLogListProperties = CaptureListProperties.from_context(context).last_resut_log
            if rll.has_any_errors_or_warnings:
                box = layout.box()
                row = box.row()
                row.label(text="Last bake:")
                row = box.row()
                if rll.errors:
                    row.alert = True
                    row.label(text=f"{len(list(rll.errors))} errors", icon="ERROR")
                if rll.warning:
                    row.alert = False
                    row.label(text=f"{len(list(rll.warnings))} warnings", icon="ERROR")
                row.operator(ShowResultLogDetails.bl_idname, text="", icon="ZOOM_PREVIOUS")
            # op.star

        except Exception as e:
            ui_utils.draw_error(self.layout, f"Unexpected error. \n {e}")
            raise
        finally:
            self.ctx = None
