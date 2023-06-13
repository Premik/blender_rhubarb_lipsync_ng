from ast import List
from time import sleep
from concurrent.futures import thread
from typing import Iterable
import unittest
from functools import cached_property
from pathlib import Path
from bl_ui import register

import bpy
from bpy.props import PointerProperty

import rhubarb_lipsync
import rhubarb_lipsync.blender.auto_load
import sample_data
import rhubarb_lipsync.blender.rhubarb_operators as rhubarb_operators
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, MouthCueList, JobProperties, MouthCueListItem
from rhubarb_lipsync.blender.mapping_properties import MappingProperties
from rhubarb_lipsync.rhubarb.log_manager import logManager
import rhubarb_lipsync.blender.ui_utils as ui_utils
import sample_data
import addon_utils


class SampleProject:
    """Manages Blender test project"""

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
        # Make sure the addon gets listed in the ctx.addons preferences. This is probably a hack
        addon_utils._addon_ensure(RhubarbAddonPreferences.bl_idname)
        SampleProject.registered = True

    @cached_property
    def sample(self) -> sample_data.SampleData:
        return sample_data.snd_en_male_electricity

    def create_capture(self) -> None:
        bpy.ops.rhubarb.create_capture_props()  # Create new capture item
        props = self.cprops
        assert props
        props.sound = self.sample.to_sound(bpy.context)

    def trigger_capture(self) -> None:
        ret = bpy.ops.rhubarb.process_sound_file()
        assert 'RUNNING_MODAL' in ret

    def wait_for_capture_finish(self) -> None:
        assert self.jprops
        last = 0
        loops = 0
        while self.jprops.status == "Running":
            sleep(0.1)
            op = rhubarb_operators.ProcessSoundFile.last_op
            if not op:
                break

            op.modal(bpy.context, None)
            if self.jprops.progress > last:
                loops = 0
            loops += 1
            assert loops < 50, f"Got not progress update after 5 secs {last}"
        assert self.jprops.status == "Done", f"Capture failed {self.jprops.status} {self.jprops.error}"

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
        return self.cprops and self.cprops.cue_list

    @property
    def cue_items(self) -> list[MouthCueListItem]:
        return self.cue_list and self.cue_list.items or []

    def assert_cues_matches_sample(self) -> None:
        cues = self.sample.expected_cues
        assert len(cues) == len(self.cue_items), f"Expected {len(cues)} cues, got {self.cue_items} "
        for i, c in enumerate(self.cue_items):
            c_exp = cues[i]
            assert c.cue == c_exp, f"Got {c.cue} at position {i} while {c_exp} was expected"

    def capture(self) -> None:
        self.create_capture()
        self.trigger_capture()
        self.wait_for_capture_finish()
        self.assert_cues_matches_sample()

    def ensure_action(self, name: str) -> bpy.types.Action:
        if name in bpy.data.actions.keys():
            return bpy.data.actions[name]
        a = bpy.data.actions.new(name)
        assert a.name == name, f"Name clash. Got '{a.name}' name instead of '{name}'"
        fc = a.fcurves.new('location', index=1)
        fc.keyframe_points.insert(1, 1)
        return a

    @property
    def action_single(self) -> bpy.types.Action:
        """Action with singe keyframe `location.x@1=1`"""
        return self.ensure_action('action_signle')

    @property
    def action_10(self) -> bpy.types.Action:
        """Action with two keyframes: `location.x@1=1` `location.x@10=10`"""
        if 'action_10' in bpy.data.actions.keys():
            return  # Already created
        a = self.ensure_action('action_10')
        a.fcurves[0].keyframe_points.insert(10, 10)
        return a

    @property
    def sphere1(self) -> bpy.types.Object:
        if 'Sphere' in bpy.data.objects.keys():
            return bpy.data.objects['Sphere']

        ui_utils.assert_op_ret(bpy.ops.mesh.primitive_uv_sphere_add())
        ret = bpy.context.active_object
        assert ret.name == 'Sphere'
        return ret
