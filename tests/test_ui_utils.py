import unittest
from functools import cached_property
from pathlib import Path

import bpy
from bpy.props import PointerProperty

import rhubarb_lipsync
import rhubarb_lipsync.blender.auto_load
import rhubarb_lipsync.blender.ui_utils as ui_utils
import test_data
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.blender.capture_properties import CaptureProperties

# def setUpModule():
#    rhubarb_lipsync.register()  # Simulate blender register call


class PropertiesTest(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
