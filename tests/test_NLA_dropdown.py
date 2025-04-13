from time import sleep
import unittest
from dataclasses import dataclass

import rhubarb_lipsync.blender.baking_utils as baking_utils
from rhubarb_lipsync.blender.mapping_properties import NlaTrackRef
import sample_project
import bpy
from rhubarb_lipsync.rhubarb.log_manager import logManager


class NLADropdownTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        self.project.create_mapping_1action_on_armature()
        self.create_tracks()
        logManager.set_trace()

    def create_track(self, name: str) -> None:
        o = bpy.context.object
        assert o, "No object active"
        ad = o.animation_data
        if not ad:
            o.animation_data_create()
            ad = o.animation_data
        tracks = ad.nla_tracks
        t = tracks.new()
        t.name = name

    def create_tracks(self) -> None:
        self.create_track("VeryFirst")
        self.project.add_track1()
        self.create_track("Middle")
        self.project.add_track2()
        self.create_track("End")
        ad = bpy.context.object.animation_data
        self.assertGreaterEqual(len(ad.nla_tracks), 5)
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
        self.assertIsNotNone(track_ref.selected_item, f"{msg} Track reference should have a selected item. \n{tracks}")
        self.assertEqual(track_ref.index, expected_index, f"{msg} Track index should be {expected_index}, but is {track_ref.index} \n{tracks}")
        self.assertIn(
            "RLPS Track", track_ref.selected_item.name, f"{msg} Track name should contain 'RLPS Track', but is '{track_ref.selected_item.name}' \n{tracks}"
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
        ad.nla_tracks[3].name = "NEW_PREFIX RLPS Track 2"
        self.verify_rlps_tracks(1, 3)

    def testDeleteLastTrack(self) -> None:
        ad = bpy.context.object.animation_data
        ad.nla_tracks.remove(ad.nla_tracks[4])  # Remove "End" track
        self.verify_rlps_tracks(1, 3)  # Should stay the same

    def testDeleteMiddleTrack(self) -> None:
        ad = bpy.context.object.animation_data
        for i, track in enumerate(ad.nla_tracks):
            if i != 2:
                track.select = False
        bpy.ops.nla.tracks_delete()

        # ad.nla_tracks.remove(ad.nla_tracks[2])

        # Verify track references - track1 should still be at index 1,
        # but track2 should now be at index 2 since the track before it was removed
        self.verify_rlps_tracks(1, 2, "After deleting middle track")

    def testDeleteFirstTrack(self) -> None:
        ad = bpy.context.object.animation_data
        ad.nla_tracks.remove(ad.nla_tracks[0])
        # Verify track references - both should be shifted down by 1
        self.verify_rlps_tracks(0, 2, "After deleting first track")

    def testMoveFirstTrackDown(self) -> None:
        # Move "VeryFirst" track down (swap with RLPS Track 1)
        ad = bpy.context.object.animation_data
        very_first_track = ad.nla_tracks[0]
        # In Blender, moving a track down means increasing its index
        very_first_track.select = True
        # Deselect all other tracks
        for i, track in enumerate(ad.nla_tracks):
            if i != 0:
                track.select = False
        # Set the active track
        ad.nla_tracks.active = very_first_track
        # Move the track down (swap positions)
        bpy.ops.anim.channels_move(direction='DOWN')

        # After moving, the RLPS Track 1 should be at index 0 and VeryFirst at index 1
        # Track references should adjust accordingly
        self.verify_rlps_tracks(0, 3, "After moving first track down")

        # Verify the track names at their new positions
        self.assertEqual(ad.nla_tracks[0].name, self.track1.selected_item.name, "RLPS Track 1 should be at index 0")
        self.assertEqual(ad.nla_tracks[1].name, "VeryFirst", "VeryFirst track should be at index 1")

    def testDeleteRLPSTrack(self) -> None:
        # Delete one of the RLPS tracks (track1)
        ad = bpy.context.object.animation_data
        rlps_track_index = self.track1.index
        ad.nla_tracks.remove(ad.nla_tracks[rlps_track_index])

        # Now track2 should still exist with adjusted index
        # track1 should be None or invalid
        o: bpy.Object = self.track1.object
        tracks = [t.name for t in o.animation_data.nla_tracks]

        self.assertIsNone(self.track1.selected_item, f"track1 should be None after deletion \n{tracks}")
        # track2 should be at index 2 (original 3 minus 1 for deleted track)
        self.verify_rlps_track(self.track2, 2, "After deleting RLPS track1")


if __name__ == "__main__":
    unittest.main()
