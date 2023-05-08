import logging
import pathlib
from io import TextIOWrapper
from typing import Dict, List, Optional, cast

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, Sound, SoundSequence

import rhubarb_lipsync.blender.mapping_operators as mapping_operators
import rhubarb_lipsync.blender.rhubarb_operators as rhubarb_operators
import rhubarb_lipsync.blender.sound_operators as sound_operators
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.mapping_list import MappingUIList
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences, MappingListPreferences
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, MouthCueList, JobProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties
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
        mlp: MappingListPreferences = prefs.mapping_list_prefs
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

    def draw_nla_setup(self) -> None:
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        mprops: MappingProperties = MappingProperties.from_context(self.ctx)
        layout = self.layout
        row = layout.row(align=True)
        layout.prop(mprops.nla_track1, 'name', text="NLA Track 1")
        layout.prop(mprops.nla_track2, 'name', text="NLA Track 2")

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
            self.draw_config()
            self.draw_mapping_list()
            self.draw_nla_setup()

        except Exception as e:
            ui_utils.draw_error(self.layout, f"Unexpected error. \n {e}")
            raise
        finally:
            self.ctx = None
