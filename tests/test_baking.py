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
        p = self.project
        p.capture()
        p.initialize_mapping(p.sphere1)  # Sphere becomes active
        p.create_mapping([p.action_single])  # Single frame action for all cues on the sphere
        self.bc = baking_utils.BakingContext(bpy.context)
        # assert len(self.bc.objects) > 0
        self.bc.next_object()
        assert self.bc.current_object, f"No object selected from the {self.bc.objects}"

    def testBasic(self) -> None:
        assert len(self.bc.objects) == 1, "No active object"
        assert len(self.bc.cue_items) > 1, "No cues in the capture"
        assert self.bc.frame_range == (1, 26)

    def testTrackValidation(self) -> None:
        errs = self.bc.validate_track()
        assert len(errs) > 0
        assert not self.bc.current_track
        self.project.add_track1()
        self.bc.next_track()
        assert self.bc.current_object, "No object selected"
        assert self.bc.current_track
        errs = self.bc.validate_track()
        assert len(errs) == 0, errs[0]


if __name__ == '__main__':
    unittest.main()
