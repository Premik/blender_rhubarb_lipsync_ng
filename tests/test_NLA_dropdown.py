import unittest

import bpy

import rhubarb_lipsync.blender.ui_utils as ui_utils
import sample_project
from rhubarb_lipsync.blender.mapping_properties import NlaTrackRef
from rhubarb_lipsync.rhubarb.log_manager import logManager


class NLADropdownTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        self.project.create_mapping_1action_on_armature()
        self.create_tracks()
        logManager.set_trace()

    def create_trackDirect(self, name: str) -> None:
        o = bpy.context.object
        assert o, "No object active"
        ad = o.animation_data
        if not ad:
            o.animation_data_create()
            ad = o.animation_data
        tracks = ad.nla_tracks
        t = tracks.new()
        t.name = name

    def create_track(self, name: str) -> None:
        o = bpy.context.object
        assert o, "No object active"
        ui_utils.assert_op_ret(bpy.ops.rhubarb.create_object_nla_track(object_name=o.name, track_name=name))

    def create_tracks(self) -> None:
        self.create_track("VeryFirst")
        self.project.add_track1()
        self.create_track("Middle")
        self.project.add_track2()
        self.create_track("End")
        ad = bpy.context.object.animation_data
        self.assertGreaterEqual(len(ad.nla_tracks), 5)
        self.trigger_depsgraph()
        self.verify_rlps_tracks(1, 3)

    @property
    def track1(self) -> NlaTrackRef:
        return self.project.mprops.nla_track1

    @property
    def track2(self) -> NlaTrackRef:
        return self.project.mprops.nla_track2

    def verify_rlps_track(self, track_ref: NlaTrackRef, expected_index: int, msg: str = "") -> None:
        """Verify that the track reference points to a valid RLPS track with the expected index"""
        o: bpy.Object = track_ref.object
        tracks = [t.name for t in o.animation_data.nla_tracks]

        # Create a formatted track list with indices, highlighting the selected track
        formatted_tracks = []
        for i, track in enumerate(tracks):
            if i == track_ref.index:
                formatted_tracks.append(f"[{i}:{track}]".ljust(20))
            else:
                formatted_tracks.append(f"{i}:{track}".ljust(20))
        track_list_str = "|".join(formatted_tracks)

        self.assertIsNotNone(track_ref.selected_item, f"{msg} Track reference should have a selected item.\n{track_list_str}")
        self.assertEqual(track_ref.index, expected_index, f"{msg} Track index should be {expected_index}, but is {track_ref.index}\n{track_list_str}")
        self.assertIn(
            "RLPS Track",
            track_ref.selected_item.name,
            f"{msg} Track name should contain 'RLPS Track', but is '{track_ref.selected_item.name}'\{track_list_str}",
        )

    def verify_rlps_tracks(self, expected_index1: int, expected_index2: int, msg: str = "") -> None:
        """Verify both track references point to valid RLPS tracks with the expected indices"""
        self.verify_rlps_track(self.track1, expected_index1, f"Track1: {msg}")
        self.verify_rlps_track(self.track2, expected_index2, f"Track2: {msg}")

    def testBasic1Action(self) -> None:
        assert self.track1.index
        print(self.track1)
        print(self.track2)
        self.verify_rlps_tracks(1, 3)  # Initially track1 is at index 1, track2 is at index 3

    def testRenameTrack2(self) -> None:
        # Rename track2 but keep RLPS Track in the name
        ad = bpy.context.object.animation_data
        self.trigger_depsgraph()
        ad.nla_tracks[3].name = "NEW_PREFIX RLPS Track 2"

        self.verify_rlps_tracks(1, 3)

    def testDeleteLastTrack(self) -> None:
        ad = bpy.context.object.animation_data
        # ad.nla_tracks.remove(ad.nla_tracks[4])  # Remove "End" track
        ui_utils.assert_op_ret(bpy.ops.rhubarb.delete_object_nla_track(object_name=bpy.context.object.name, track_index=4))
        self.verify_rlps_tracks(1, 3)  # Should stay the same

    def testDeleteMiddleTrack(self) -> None:
        ad = bpy.context.object.animation_data
        ui_utils.assert_op_ret(bpy.ops.rhubarb.delete_object_nla_track(object_name=bpy.context.object.name, track_index=2))

        # Verify track references - track1 should still be at index 1,
        # but track2 should now be at index 2 since the track before it was removed
        self.verify_rlps_tracks(1, 2, "After deleting middle track")

    def testDeleteFirstTrack(self) -> None:
        ad = bpy.context.object.animation_data
        ui_utils.assert_op_ret(bpy.ops.rhubarb.delete_object_nla_track(object_name=bpy.context.object.name, track_index=0))
        # Verify track references - both should be shifted down by 1
        self.verify_rlps_tracks(0, 2, "After deleting first track")

    @unittest.skip("When track is moved with an operation the change is somehow not (instantly?) propagate")
    def testMoveFirstTrackDown(self) -> None:
        # Move "VeryFirst" track down (swap with RLPS Track 1)
        ad = bpy.context.object.animation_data
        very_first_track = ad.nla_tracks[0]
        very_first_track.select = True
        ad.nla_tracks.active = very_first_track

        area = None
        for a in bpy.context.screen.areas:
            print(a.type)
            if a.type == 'OUTLINER':
                area = a
                area.type = 'NLA_EDITOR'
                region = None
                for r in area.regions:
                    if r.type == 'WINDOW':
                        region = r
                        break
                break
        else:
            # If no dopesheet editor is open, we may need to create one or skip the test
            self.skipTest("No outliner area found to convert to NLA editor")

        if region is None:
            self.skipTest("Could not find WINDOW region in NLA editor")
        # Use the temp_override context manager
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.anim.channels_move(direction='DOWN')

        # for area in bpy.context.screen.areas:
        #     if area.type == 'VIEW_3D':
        #         override = bpy.context.copy()
        #         override["area"] = area
        #         with bpy.context.temp_override(**override):
        #             bpy.ops.anim.channels_move(direction='DOWN')
        #         break

        # After moving, the RLPS Track 1 should be at index 0 and VeryFirst at index 1
        self.verify_rlps_tracks(0, 3, "After moving first track down")

        # Verify the track names at their new positions
        self.assertEqual(ad.nla_tracks[0].name, self.track1.selected_item.name, "RLPS Track 1 should be at index 0")
        self.assertEqual(ad.nla_tracks[1].name, "VeryFirst", "VeryFirst track should be at index 1")

    def trigger_depsgraph(self) -> None:
        # ui_utils.assert_op_ret(bpy.ops.rhubarb.show_placement_help())
        ui_utils.assert_op_ret(bpy.ops.rhubarb.dummy_op())

    def testDeleteRLPSTrack(self) -> None:
        # Delete one of the RLPS tracks (track1)
        # ad = bpy.context.object.animation_data
        # del self.project
        # self.setUp()
        rlps_track_index = self.track1.index

        ui_utils.assert_op_ret(bpy.ops.rhubarb.delete_object_nla_track(object_name=bpy.context.object.name, track_index=rlps_track_index))

        # Now track2 should still exist with adjusted index
        # track1 should be None or invalid
        o: bpy.Object = self.track1.object
        tracks = [t.name for t in o.animation_data.nla_tracks]

        self.assertIsNone(self.track1.selected_item, f"track1 should be None after deletion \n{tracks}")
        # track2 should be at index 2 (original 3 minus 1 for deleted track)
        self.verify_rlps_track(self.track2, 2, "After deleting RLPS track1")


class NLADropdownTest2(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        self.project.create_mapping_1action_on_armature()
        # self.create_tracks()
        logManager.set_trace()

    def testBasic1Action(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
