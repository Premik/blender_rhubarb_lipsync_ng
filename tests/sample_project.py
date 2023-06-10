import unittest
from functools import cached_property
from pathlib import Path
from bl_ui import register

import bpy
from bpy.props import PointerProperty

import rhubarb_lipsync
import rhubarb_lipsync.blender.auto_load
import sample_data
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, MouthCueList, JobProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties
from rhubarb_lipsync.rhubarb.log_manager import logManager
import rhubarb_lipsync.blender.ui_utils as ui_utils
import sample_data
import addon_utils


class SampleProject:
    registered = False

    def __init__(self) -> None:
        SampleProject.ensure_registered()

    @staticmethod
    def ensure_registered() -> None:
        if SampleProject.registered:
            return
        rhubarb_lipsync.register()  # Simulate blender register call
        logManager.set_debug()

        # bpy.context.preferences.addons['rhubarb_lipsync'].preferences = bpy.context.preferences.addons['rhubarb_lipsync'].preferences
        addon_utils._addon_ensure('rhubarb_lipsync')
        SampleProject.registered = True

    def create_capture(self) -> None:
        bpy.ops.rhubarb.create_capture_props()  # Create new capture item
        props = self.cprops
        assert props
        props.sound = sample_data.snd_en_male_watchingtv.to_sound(bpy.context)

    def add_objects(self) -> None:
        ui_utils.assert_op_ret(bpy.ops.mesh.primitive_cylinder_add())

    @property
    def cprops(self) -> CaptureProperties:
        return CaptureListProperties.capture_from_context(bpy.context)

    @property
    def jprops(self) -> JobProperties:
        return self.cprops and self.cprops.job

    @property
    def cue_list(self) -> MouthCueList:
        return self.cprops and self.cue_list
