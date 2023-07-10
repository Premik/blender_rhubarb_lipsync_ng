import unittest

import bpy

import rhubarb_lipsync.blender.ui_utils as ui_utils
import sample_project


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
