import logging
import pathlib
from io import TextIOWrapper
from typing import Dict, List, Optional, cast

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, Sound, SoundSequence, UILayout

import rhubarb_lipsync.blender.baking_operators as baking_operators
import rhubarb_lipsync.blender.mapping_operators as mapping_operators
import rhubarb_lipsync.blender.rhubarb_operators as rhubarb_operators
import rhubarb_lipsync.blender.sound_operators as sound_operators
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.mapping_list import MappingUIList
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences, MappingPreferences
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, MouthCueList, JobProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, NlaTrackRef
from rhubarb_lipsync.blender.ui_utils import IconsManager
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfo, MouthShapeInfos
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob

log = logging.getLogger(__name__)


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
        layout = self.layout
        layout.label(text=MappingListOptionsPanel.bl_label)
        # layout.prop(mlp, "actions_multiline_view") # Doesn't work
        layout.prop(mlp, "show_help_button")
        layout.prop(clp, "as_circle")


class MappingAndBakingPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_map_and_bake"
    bl_label = "RLPS: Cue mapping and baking"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RLSP"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_config(self) -> None:
        mprops: MappingProperties = MappingProperties.from_context(self.ctx)
        layout = self.layout
        row = layout.row(align=True)
        row.prop(mprops, 'nla_map_action', toggle=True)
        row.prop(mprops, 'nla_map_shapekey', toggle=True)
        row.popover(panel=MappingListOptionsPanel.bl_idname, text="", icon="VIS_SEL_11")

    def draw_mapping_list(self) -> None:
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        mprops: MappingProperties = MappingProperties.from_context(self.ctx)

        layout = self.layout

        row = layout.row(align=True)
        layout.template_list(MappingUIList.bl_idname, "Mapping", mprops, "items", mprops, "index")

    def draw_nla_track_picker(self, ctx: Context, track_field_name: str, text: str) -> None:
        row = self.layout.row(align=True)
        mprops: MappingProperties = MappingProperties.from_context(self.ctx)
        track: NlaTrackRef = getattr(mprops, track_field_name)
        row.prop(track, 'name', text=text)
        # row.prop(track, 'index')
        op: mapping_operators.CreateNLATrack = row.operator(mapping_operators.CreateNLATrack.bl_idname, text="", icon="DUPLICATE")
        obj_name = self.ctx.object and self.ctx.object.name or ''
        op.name = f"RLPS {obj_name} {text}"
        op.track_field_name = track_field_name
        # op.trackRef=track

        # row.operator(capture_operators.DeleteCaptureProps.bl_idname, text="", icon="PANEL_CLOSE")

    def draw_nla_setup(self) -> None:
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        mprops: MappingProperties = MappingProperties.from_context(self.ctx)

        self.draw_nla_track_picker(self.ctx, "nla_track1", "Track 1")
        self.draw_nla_track_picker(self.ctx, "nla_track2", "Track 2")

    def draw(self, context: Context) -> None:
        try:
            self.ctx = context
            layout = self.layout

            selection_error = MappingProperties.context_selection_validation(context)
            if selection_error:
                ui_utils.draw_error(self.layout, selection_error)
                return
            mprops: MappingProperties = MappingProperties.from_context(context)
            cprops = CaptureListProperties.capture_from_context(self.ctx)
            if len(mprops.items) != len(MouthShapeInfos.all()):
                layout.alert = True
                layout.operator(mapping_operators.BuildCueInfoUIList.bl_idname)
                return
            self.draw_config()
            self.draw_mapping_list()
            self.draw_nla_setup()

            layout.operator(baking_operators.BakeToNLA.bl_idname, icon="LONGDISPLAY")
            # op.star

        except Exception as e:
            ui_utils.draw_error(self.layout, f"Unexpected error. \n {e}")
            raise
        finally:
            self.ctx = None
