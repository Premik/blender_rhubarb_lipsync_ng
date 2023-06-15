import unittest
from functools import cached_property
from pathlib import Path

import bpy
from bpy.props import PointerProperty

import rhubarb_lipsync
import rhubarb_lipsync.blender.auto_load
import sample_data, sample_project
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, MouthCueList, JobProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties
from rhubarb_lipsync.rhubarb.log_manager import logManager


class PropertiesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        self.project.create_capture()
        assert self.project.cprops

    def testSoundFilePath(self) -> None:
        props = self.project.cprops

        self.assertEqual(props.sound_file_extension, 'ogg')
        self.assertEqual(props.sound_file_basename, 'en_male_electricity')
        self.assertIn('data', props.sound_file_folder)
        self.assertTrue(props.is_sound_format_supported())

        newName = self.project.cprops.get_sound_name_with_new_extension("wav")
        self.assertEqual(newName, 'en_male_electricity.wav')


if __name__ == '__main__':
    unittest.main()
