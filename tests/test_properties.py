import unittest
from functools import cached_property
from pathlib import Path

import bpy
from bpy.props import PointerProperty

import rhubarb_lipsync
import rhubarb_lipsync.blender.auto_load
import test_data
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.blender.properties import CaptureProperties
from rhubarb_lipsync.rhubarb.log_manager import logManager


def setUpModule():
    rhubarb_lipsync.register()  # Simulate blender register call
    logManager.set_debug()


class PropertiesTest(unittest.TestCase):
    def setUp(self):

        # There is the default cube already..
        # bpy.ops.mesh.primitive_cube_add()
        # obj = bpy.context.object
        # assert obj
        self.props = CaptureProperties.from_context(bpy.context)
        assert self.props

    def testSoundFilePath(self):
        props = self.props
        props.sound = test_data.snd_en_male_watchingtv.to_sound(bpy.context)

        self.assertEqual(props.sound_file_extension, 'ogg')
        self.assertEqual(props.sound_file_basename, 'en_male_watchingtv')
        self.assertIn('data', props.sound_file_folder)
        self.assertTrue(props.is_sound_format_supported())

        newName = self.props.get_sound_name_with_new_extension("wav")
        self.assertEqual(newName, 'en_male_watchingtv.wav')


if __name__ == '__main__':
    unittest.main()
