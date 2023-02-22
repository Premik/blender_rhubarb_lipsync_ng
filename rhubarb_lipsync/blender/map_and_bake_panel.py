import logging
import pathlib
from io import TextIOWrapper
from typing import Dict, List, Optional, cast

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, Sound, SoundSequence

import rhubarb_lipsync.blender.rhubarb_operators as rhubarb_operators
import rhubarb_lipsync.blender.sound_operators as sound_operators
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences, CueListPreferences
from rhubarb_lipsync.blender.properties import CaptureProperties, MappingList, MappingListItem
from rhubarb_lipsync.blender.ui_utils import IconsManager
from rhubarb_lipsync.blender.mapping_list import MappingUIList
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob

log = logging.getLogger(__name__)


class CaptureMouthCuesPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_map_and_bake"
    bl_label = "RLPS: Cue mapping and baking"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RLSP"

    def draw_mapping_list(self) -> None:
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        props = CaptureProperties.from_context(self.ctx)

        layout = self.layout

        row = layout.row(align=True)
        lst: MappingList = props.mapping
        layout.template_list(MappingUIList.bl_idname, "Mapping", lst, "items", lst, "index")

    def draw(self, context: Context):
        try:
            props = CaptureProperties.from_context(context)
            self.ctx = context
            layout = self.layout

            selection_error = CaptureProperties.context_selection_validation(context)
            if selection_error:
                ui_utils.draw_error(self.layout, selection_error)
            else:
                self.draw_mapping_list()

        except Exception as e:
            ui_utils.draw_error(self.layout, f"Unexpected error. \n {e}")
            raise
        finally:
            self.ctx = None  # type: ignore
