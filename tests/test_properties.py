from functools import cached_property
from pathlib import Path
import unittest
import bpy
from bpy.props import PointerProperty
import test_data
import rhubarb_lipsync
import rhubarb_lipsync.blender.auto_load
from rhubarb_lipsync.blender.properties import CaptureProperties


class PropertiesTest(unittest.TestCase):
    def setUp(self):

        rhubarb_lipsync.register()  # Simulate blender register call
        # There is the default cube already..
        # bpy.ops.mesh.primitive_cube_add()
        # obj = bpy.context.object
        # assert obj
        self.props = CaptureProperties.from_context(bpy.context)
        assert self.props

    def testSoundFilePath(self):
        props = self.props
        props.sound = test_data.snd_en_male_watchingtv.to_sound(bpy.context)

        self.assertEqual(props.sound_file_extension, 'ext')


if __name__ == '__main__':
    unittest.main()
