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
import rhubarb_lipsync.blender.baking_utils as baking_utils
import sample_data, sample_project


class BakingContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        self.project.capture()

    def testBasic(self) -> None:
        self.bc = self.project.create_mapping_single_sphere1()
        assert len(self.bc.objects) == 1, "No active object"
        assert len(self.bc.cue_items) > 1, "No cues in the capture"
        assert self.bc.frame_range == (1, 26)

    def testTrackValidation(self) -> None:
        self.bc = self.project.create_mapping_single_sphere1()
        errs = self.bc.validate_track()
        assert len(errs) > 0
        assert not self.bc.current_track
        self.project.add_track1()
        self.bc.next_track()
        assert self.bc.current_object, "No object selected"
        assert self.bc.current_track
        errs = self.bc.validate_track()
        assert len(errs) == 0, errs[0]

    def testBakeTwoTracks(self) -> None:
        self.bc = self.project.create_mapping_single_sphere1()
        self.project.add_track1()
        self.project.add_track2()
        assert self.bc.has_two_tracks
        for o in self.bc.object_iter():
            errs = self.bc.validate_selection()
            assert len(errs) == 0, errs[0]
        ui_utils.assert_op_ret(bpy.ops.rhubarb.bake_to_nla())
        assert not self.project.clist_props.last_error, self.project.clist_props.last_error


if __name__ == '__main__':
    unittest.main()
