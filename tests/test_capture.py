import unittest
from functools import cached_property
from pathlib import Path

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
import sample_data, sample_project


class CaptureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        self.project.create_capture()
        assert self.project.cprops

    def testGetVer(self) -> None:
        ui_utils.assert_op_ret(bpy.ops.rhubarb.get_executable_version())

    def testCaputre(self) -> None:
        self.project.trigger_capture()
        self.project.wait_for_capture_finish()
        self.project.assert_cues_matches_sample()
        print("done")


if __name__ == '__main__':
    unittest.main()
