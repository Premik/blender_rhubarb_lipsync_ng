import unittest

import bpy

import rhubarb_lipsync.blender.ui_utils as ui_utils
import sample_project


class BakingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        # Set the trim-long-cues to hight number to avoid trimming for test consistency (extra X cues)
        self.project.prefs.cue_list_prefs.highlight_long_cues = 1
        self.project.capture_load_json()

    def bake(self) -> None:
        for _ in self.bc.object_iter():
            # errs = self.bc.validate_selection()
            errs = self.bc.validate_current_object()
            self.assertFalse(errs, errs)
        ui_utils.assert_op_ret(bpy.ops.rhubarb.bake_to_nla())
        self.assertFalse(list(self.project.last_result.errors), list(self.project.last_result.items))
        # Trimming warnings are ok
        w = self.project.last_result.warnings
        w = [w for w in w if "Had to trim" not in w.msg]
        self.assertFalse(w, list(self.project.last_result.items))
        cues, strips = self.project.parse_last_bake_result_details()
        self.assertGreater(strips, 1, "No strips baked")
        self.assertEqual(strips % cues, 0, f"Number of strips ({strips}) created doesn't match the number of captured cues ({cues})")
        self.assertEqual(
            len(self.project.cue_items), cues, f"Number of baked cues ({cues}) doesn't match the number of cues in the capture ({self.project.cue_items})"
        )
        for _ in self.bc.object_iter():
            for t in (self.bc.track1, self.bc.track2):
                if t:
                    self.assertGreater(len(t.strips), 1, f"Track {t} was empty after the bake")

    def bakeTwoTracks(self) -> None:
        for o in self.bc.object_iter():
            self.project.make_object_active(o)
            self.project.add_track1()
            self.project.add_track2()
            self.assertTrue(self.bc.has_two_tracks)
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
        self.assertFalse(self.bc.has_two_tracks)
        self.bake()

    def testBake2Tracks1ShapekeyAction(self) -> None:
        self.bc = self.project.create_mapping_1action_on_mesh()
        self.bakeTwoTracks()

    def testBakeTwoObjects(self) -> None:
        self.bc = self.project.create_mapping_two_objects()
        self.bakeTwoTracks()
        # self.project.save_blend_file("/tmp/work/1.blend")

    def testBakeActionSheet(self) -> None:
        self.bc = self.project.create_mapping_sheet()
        self.bakeTwoTracks()


if __name__ == "__main__":
    unittest.main()
