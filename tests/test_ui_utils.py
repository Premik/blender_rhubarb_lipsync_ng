from typing import Sequence
import unittest
from functools import cached_property
from pathlib import Path

from colorama import init

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


class MockDropdown:
    def __init__(self, lst: Sequence) -> None:
        self.items = lst
        self.index = 0
        self.name = ""

    def item2str(self, item) -> str:
        return str(item)


class DrowpdownHelperTest(unittest.TestCase):
    # def setUp(self) -> None:
    #    self.blank = DropdownHelper()

    def testIndexEmpty(self) -> None:
        d = ui_utils.DropdownHelper(MockDropdown([]))
        d.ensure_index_bounds()
        self.assertEqual(len(d.items), 0)
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)

    def testAdding(self) -> None:
        lst: list[str] = []
        d = ui_utils.DropdownHelper(MockDropdown(lst))
        lst.append("aa")
        d.ensure_index_bounds()
        self.assertEqual(d.index, 0, "Originally invalid index didn't change to the first item")
        lst.append("bb")
        d.ensure_index_bounds()
        self.assertEqual(d.index, 0)
        self.assertEqual(d.name, "")

    def testIndex2Name(self) -> None:
        lst: list[str] = ["aa", "bb", "cc"]
        d = ui_utils.DropdownHelper(MockDropdown(lst))
        self.assertEqual(d.index, 0)
        self.assertEqual(d.name, "")
        d.index2name()
        self.assertEqual(d.name, "aa")
        d.index = 10
        d.index2name()
        self.assertEqual(d.name, "cc")

    def testName2index(self) -> None:
        lst: list[str] = ["000 aa", "001:bb", "2 cc"]
        d = ui_utils.DropdownHelper(MockDropdown(lst))
        self.assertEqual(d.index, 0)
        d.name2index()
        self.assertEqual(d.index, 0)
        d.nameNotFoundHandling = ui_utils.DropdownHelper.NameNotFoundHandling.UNSELECT
        d.name2index()
        self.assertEqual(d.index, -1)
        d.name = "001 foo"
        d.name2index()
        self.assertEqual(d.index, 1)


if __name__ == '__main__':
    unittest.main()
