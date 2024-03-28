import unittest
from dataclasses import dataclass

import bpy

import rhubarb_lipsync.blender.baking_utils as baking_utils
import rhubarb_lipsync.blender.ui_utils as ui_utils
import sample_project


@dataclass
class MockStrip:
    frame_start: float
    frame_end: float


@dataclass
class MockTrack:
    strips: list[MockStrip]


class BakingUtilsTest(unittest.TestCase):
    s0 = MockStrip(1, 10)
    s1 = MockStrip(10, 20)
    s2 = MockStrip(30, 100)

    t1 = MockTrack([s0, s1, s2])

    def testFindStrips(self) -> None:
        self.assertEqual(baking_utils.find_strip_at(BakingUtilsTest.t1, 0)[0], -1)
        self.assertEqual(baking_utils.find_strip_at(BakingUtilsTest.t1, 1.1)[0], 0)
        self.assertEqual(baking_utils.find_strip_at(BakingUtilsTest.t1, 1)[0], 0)
        self.assertEqual(baking_utils.find_strip_at(BakingUtilsTest.t1, 5)[0], 0)
        self.assertEqual(baking_utils.find_strip_at(BakingUtilsTest.t1, 19)[0], 1)
        self.assertEqual(baking_utils.find_strip_at(BakingUtilsTest.t1, 25)[0], -1)
        self.assertEqual(baking_utils.find_strip_at(BakingUtilsTest.t1, 20)[0], -1)
        self.assertEqual(baking_utils.find_strip_at(BakingUtilsTest.t1, 40)[0], 2)
        self.assertEqual(baking_utils.find_strip_at(BakingUtilsTest.t1, 200)[0], -1)


class BakingContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        self.project.capture_load_json()

    def basic_asserts(self) -> None:
        assert len(self.bc.objects) == 1, "No active object"
        assert len(self.bc.mouth_cue_items) > 1, "No cues in the capture"
        assert self.bc.total_frame_range == (1, 26)

    def testBasic1Action(self) -> None:
        self.bc = self.project.create_mapping_1action_on_armature()
        self.basic_asserts()

    def testBasicTwoActions(self) -> None:
        self.bc = self.project.create_mapping_2actions_on_armature()
        self.basic_asserts()

    def trackValidation(self) -> None:
        errs = self.bc.validate_track()
        assert len(errs) > 0, f"Expected validation error since a track is not selected {errs}"
        print(self.bc.tracks)
        assert not self.bc.current_track
        self.project.add_track1()
        self.bc.next_track()
        assert self.bc.current_object, "No object selected"
        assert self.bc.current_track, "No current track"
        errs = self.bc.validate_track()
        assert len(errs) == 0, errs[0]

    def testTrackValidation_1action(self) -> None:
        self.bc = self.project.create_mapping_1action_on_armature()
        self.trackValidation()

    def testTrackValidation_2actions(self) -> None:
        self.bc = self.project.create_mapping_2actions_on_armature()
        self.trackValidation()

    def bake(self) -> None:
        for o in self.bc.object_iter():
            # errs = self.bc.validate_selection()
            errs = self.bc.validate_current_object()
            assert len(errs) == 0, errs[0]
        ui_utils.assert_op_ret(bpy.ops.rhubarb.bake_to_nla())
        assert not list(self.project.last_result.errors), list(self.project.last_result.items)
        # Trimming warnings are ok
        w = self.project.last_result.warnings
        w = [w for w in w if "Had to trim" not in w.msg]
        assert not w, list(self.project.last_result.items)
        cues, strips = self.project.parse_last_bake_result_details()
        assert cues == strips, f"Number of strips ({strips}) created doesn't match the number of captured cues ({cues})"
        assert len(self.project.cue_items) == cues, "Number of baked cues ({cues}) doesn't match the number of cues in the capture ({self.project.cue_items})"

    def bakeTwoTracks(self) -> None:
        self.project.add_track1()
        self.project.add_track2()
        assert self.bc.has_two_tracks
        self.bake()

    def testBake2Tracks1ActionArmature(self) -> None:
        self.bc = self.project.create_mapping_1action_on_armature()
        self.bakeTwoTracks()

    def testBake1Track1ActionsArmature(self) -> None:
        self.bc = self.project.create_mapping_1action_on_armature()
        self.project.add_track2()
        self.bake()

    def testBake2Tracks2ActionsArmature(self) -> None:
        self.bc = self.project.create_mapping_2actions_on_armature()
        self.bakeTwoTracks()

    def testBake1Tracks2ActionsArmature(self) -> None:
        self.bc = self.project.create_mapping_2actions_on_armature()
        self.project.add_track1()
        assert not self.bc.has_two_tracks
        self.bake()

    def testBake2Tracks1ShapekeyAction(self) -> None:
        self.bc = self.project.create_mapping_1action_on_mesh()
        self.bakeTwoTracks()

    def testBakeActionSheet(self) -> None:
        self.bc = self.project.create_mapping_sheet()
        self.bakeTwoTracks()
        self.project.save_blend_file("/tmp/work/1.blend")


if __name__ == "__main__":
    unittest.main()
