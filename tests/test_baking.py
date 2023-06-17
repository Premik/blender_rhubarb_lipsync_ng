import unittest
from functools import cached_property
from pathlib import Path

from pytest import skip

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

    def basic(self) -> None:
        self.bc = self.project.create_mapping_single_sphere1()
        assert len(self.bc.objects) == 1, "No active object"
        assert len(self.bc.cue_items) > 1, "No cues in the capture"
        assert self.bc.frame_range == (1, 26)

    def testBasicSingleAction(self) -> None:
        self.bc = self.project.create_mapping_single_sphere1()
        self.basic()

    def testBasicTwoActions(self) -> None:
        self.bc = self.project.create_mapping_2actions_sphere1()
        self.basic()

    def trackValidation(self) -> None:
        errs = self.bc.validate_track()
        assert len(errs) > 0, f"Expected validation error since a track is not selected {errs}"
        print(self.bc.tracks)
        assert not self.bc.current_track
        self.project.add_track1()
        self.bc.next_track()
        assert self.bc.current_object, "No object selected"
        assert self.bc.current_track
        errs = self.bc.validate_track()
        assert len(errs) == 0, errs[0]

    def testTrackValidation_signle_action(self) -> None:
        self.bc = self.project.create_mapping_single_sphere1()
        self.trackValidation()

    def testTrackValidation_two_actions(self) -> None:
        self.bc = self.project.create_mapping_2actions_sphere1()
        self.trackValidation()

    def bake(self) -> None:
        for o in self.bc.object_iter():
            errs = self.bc.validate_selection()
            assert len(errs) == 0, errs[0]
        ui_utils.assert_op_ret(bpy.ops.rhubarb.bake_to_nla())
        assert not list(self.project.last_result.errors), list(self.project.last_result.items)
        assert not list(self.project.last_result.warnings), list(self.project.last_result.items)
        cues, strips = self.project.parse_last_bake_result_details()
        assert cues == strips, f"Number of strips ({strips}) created doesn't match the number of captured cues ({cues})"
        assert len(self.project.cue_items) == cues, "Number of baked cues ({cues}) doesn't match the number of cues in the capture ({self.project.cue_items})"

    def bakeTwoTracks(self) -> None:
        self.project.add_track1()
        self.project.add_track2()
        assert self.bc.has_two_tracks
        self.bake()

    def testBakeTwoTracksSingleAction(self) -> None:
        self.bc = self.project.create_mapping_single_sphere1()
        self.bakeTwoTracks()

    def testBakeOnlyTrack2SingleAction(self) -> None:
        self.bc = self.project.create_mapping_single_sphere1()
        self.project.add_track2()
        self.bake()

    @unittest.skip("Scrip trimming, TBD")
    def testBakeTwoTracksTwoActions(self) -> None:
        self.bc = self.project.create_mapping_2actions_sphere1()
        self.bakeTwoTracks()

    @unittest.skip("Scrip trimming, TBD")
    def testBakeSingleTracksTwoActions(self) -> None:
        self.bc = self.project.create_mapping_2actions_sphere1()
        self.project.add_track1()
        assert not self.bc.has_two_tracks
        self.bake()


if __name__ == '__main__':
    unittest.main()
