import logging

import bpy
from bpy.types import Context

import rhubarb_lipsync.blender.baking_operators as baking_operators
import rhubarb_lipsync.blender.mapping_operators as mapping_operators
import rhubarb_lipsync.blender.mapping_uilist as mapping_list
import rhubarb_lipsync.blender.mapping_utils as mapping_utils
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, ResultLogListProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, NlaTrackRef
from rhubarb_lipsync.blender.misc_operators import ShowResultLogDetails
from rhubarb_lipsync.blender.preferences import CueListPreferences, MappingPreferences, RhubarbAddonPreferences, StripPlacementPreferences
from rhubarb_lipsync.rhubarb.mouth_shape_info import MouthShapeInfos

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

    # bl_category = "RLPS"

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        clp: CueListPreferences = prefs.cue_list_prefs
        mlp: MappingPreferences = prefs.mapping_prefs
        mprops: MappingProperties = MappingProperties.from_context(context)
        prefs = RhubarbAddonPreferences.from_context(context)
        layout = self.layout
        layout.label(text=MappingListOptionsPanel.bl_label)
        # layout.prop(mlp, "show_help_button")
        layout.prop(clp, "as_circle")
        layout.prop(mlp, "action_buttons_emboss")
        layout.prop(mlp, "action_dropdown_emboss")
        layout.separator()
        layout.label(text="Mapping preview on objects", icon="PLAY")
        layout.prop(prefs.mapping_prefs, "object_selection_filter_type", text="")
        layout.separator()
        layout.label(text="Action filters")
        draw_action_filters(layout, mprops, False)
        # layout.prop(mlp, "actions_multiline_view")


class MappingAndBakingPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_map_and_bake"
    bl_label = "RLPS: Cue Mapping and Baking"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RLPS"
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
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        strip_placement: StripPlacementPreferences = prefs.strip_placement
        clp: CueListPreferences = prefs.cue_list_prefs

        row = self.layout.row(align=True)

        if not ui_utils.draw_expandable_header(prefs, "strip_placement_setting_panel_expanded", "Strip Placement Settings", row):
            return
        sideRow = row.row(align=True)
        sideRow.label(text="")  # Spacer to force icons alight to the right

        # Too low-res, disabled for now
        # sideRow.operator(baking_operators.ShowPlacementHelp.bl_idname, text="", icon="QUESTION")

        # sideRow.operator(capture_operators.DeleteCaptureProps.bl_idname, text="", icon="PANEL_CLOSE")
        # img, tex = ui_utils.IconsManager.placement_help_image()
        # row = self.layout.row(align=True)
        # row.template_preview(tex, show_buttons=True)
        # row.operator("tex.preview_update")
        # row.template_image(tex, "image", tex.image_user)

        self.layout.use_property_decorate = False

        row = self.layout.row(align=True)

        row.label(text="Trim cues longer than")
        row.prop(clp, "highlight_long_cues")
        id = baking_operators.PlacementCueTrimFromPreset.bl_idname
        row.operator_menu_enum(id, "trim_preset", text="", icon="DOWNARROW_HLT")

        row = self.layout.row(align=True)
        row.prop(strip_placement, 'scale_min', text="Scale Min")
        row.prop(strip_placement, 'scale_max', text="Max")
        id = baking_operators.PlacementScaleFromPreset.bl_idname
        row.operator_menu_enum(id, "scale_type", text="", icon="DOWNARROW_HLT")
        # self.layout.prop(self.ctx.scene, "show_subframe", text="Show subframes")
        self.layout.separator()

        # row = self.layout.row(align=True)
        # row.prop(strip_placement, 'offset_start', text="Offset Start")
        # row.prop(strip_placement, 'offset_end', text="End")
        # id = baking_operators.PlacementOffsetFromPreset.bl_idname
        # row.operator_menu_enum(id, "offset_type", text="", icon="DOWNARROW_HLT")

        col = self.layout.column(align=False)
        col.use_property_split = True
        col.prop(strip_placement, 'extrapolation')

        # if not ui_utils.draw_expandable_header(prefs, "strip_blending_panel_expanded", "Strip in/out blending", self.layout):
        #     return
        col = self.layout.column(align=False)
        col.use_property_split = True
        col.prop(strip_placement, 'strip_blend_type')

        col.prop(strip_placement, 'inout_blend_type')

        row = self.layout.row(align=True)
        if strip_placement.inout_blend_type == "BY_RATIO":
            row.prop(strip_placement, 'blend_inout_ratio', text="Blend In-Out Ratio")
            id = baking_operators.PlacementBlendInOutRatioPreset.bl_idname
            row.operator_menu_enum(id, "ratio_type", text="", icon="DOWNARROW_HLT")

        # row = self.layout.row(align=True)
        # row.prop(strip_placement, 'blend_mode', expand=True)

        # blend_mode: str = strip_placement.blend_mode
        # if blend_mode == "FIXED":
        # row = self.layout.row(align=True)
        # id = baking_operators.PlacementBlendInOutFromOverlap.bl_idname
        # row.operator_menu_enum(id, "sync_type", text="", icon="DOWNARROW_HLT")

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

            layout.separator()
            row = layout.row()
            row.scale_y = 2
            row.operator(baking_operators.BakeToNLA.bl_idname, icon="NLA")
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
