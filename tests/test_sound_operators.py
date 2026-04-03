import unittest

import bpy

import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.sound_operators import find_sound_strips_by_sound
import sample_project
from helper import skip_no_aud


class SoundOperatorsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()

    @skip_no_aud
    def test_place_and_remove_strip(self) -> None:
        self.project.create_capture()
        self.project.set_capture_sound()

        self.assertEqual(len(find_sound_strips_by_sound(bpy.context)), 1)

        ui_utils.assert_op_ret(bpy.ops.rhubarb.remove_sound_strip())
        self.assertEqual(len(find_sound_strips_by_sound(bpy.context)), 0)

        ui_utils.assert_op_ret(bpy.ops.rhubarb.place_sound_strip())
        self.assertEqual(len(find_sound_strips_by_sound(bpy.context)), 1)
