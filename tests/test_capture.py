import unittest

import bpy

import rhubarb_lipsync.blender.ui_utils as ui_utils
import sample_project
from helper import skip_no_aud


class CaptureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()

    def testGetVer(self) -> None:
        self.project.create_capture()
        assert self.project.cprops
        ui_utils.assert_op_ret(bpy.ops.rhubarb.get_executable_version())

    @skip_no_aud
    def testCaputre(self) -> None:
        self.project.capture()
        print("done")


if __name__ == '__main__':
    unittest.main()
