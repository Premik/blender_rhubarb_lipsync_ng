from functools import cached_property
from pathlib import Path
import unittest
import bpy
from bpy.props import PointerProperty
import test_data
import rhubarb_lipsync
import rhubarb_lipsync.blender.auto_load
from rhubarb_lipsync.blender.properties import CaptureProperties
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
import rhubarb_lipsync.blender.ui_utils as ui_utils


# def setUpModule():
#    rhubarb_lipsync.register()  # Simulate blender register call


class PropertiesTest(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
