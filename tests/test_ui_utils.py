import unittest

import sample_project
from rhubarb_lipsync import IconsManager
from rhubarb_lipsync.blender.dropdown_helper import DropdownHelper


# def setUpModule():
#    rhubarb_lipsync.register()  # Simulate blender register call


class IconsManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()

    @unittest.skip("Seems not working for bpy as module")
    def testGetIcon(self) -> None:
        assert IconsManager.logo_icon(), "Icon id is zero. Icons loading is probably broken."


class MockDropdown:
    def __init__(self) -> None:
        self.index = -1
        self.name = ""

    def item2str(self, item) -> str:
        return str(item)


class DrowpdownHelperSelectAnyTest(unittest.TestCase):
    # def setUp(self) -> None:
    #    self.blank = DropdownHelper()

    def testIndexEmpty(self) -> None:
        d = DropdownHelper(MockDropdown(), [], DropdownHelper.NameNotFoundHandling.SELECT_ANY)
        d.ensure_index_bounds()
        self.assertEqual(len(d.names), 0)
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)

    def testAdding(self) -> None:
        lst: list[str] = []
        d = DropdownHelper(MockDropdown(), lst, DropdownHelper.NameNotFoundHandling.SELECT_ANY)
        lst.append("aa")
        d.ensure_index_bounds()
        self.assertEqual(d.index, 0, "Originally invalid index didn't change to the first item")
        lst.append("bb")
        d.ensure_index_bounds()
        self.assertEqual(d.index, 0)
        self.assertEqual(d.name, "aa")

    def testIndex2Name(self) -> None:
        lst: list[str] = ["0 aa", "1 bb", "2 cc"]
        d = DropdownHelper(MockDropdown(), lst, DropdownHelper.NameNotFoundHandling.SELECT_ANY)
        d.ensure_index_bounds()
        self.assertEqual(d.index, 0)
        self.assertEqual(d.name, "0 aa")
        d.index = 10
        d.index2name()
        self.assertEqual(d.name, "2 cc")

    @unittest.skip("For SELECT_ANY, no unselecting possible currently")
    def testUnselecting(self) -> None:
        lst: list[str] = ["aa", "bb", "cc"]
        d = DropdownHelper(MockDropdown(), lst, DropdownHelper.NameNotFoundHandling.SELECT_ANY)
        d.index = -1
        d.index2name()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)

    def testName2index(self) -> None:
        lst: list[str] = ["000 aa", "001 bb", "2 cc"]
        d = DropdownHelper(MockDropdown(), lst, DropdownHelper.NameNotFoundHandling.SELECT_ANY)
        d.index = 10
        d.name2index()
        self.assertEqual(d.index, 2)
        self.assertEqual(d.name, "2 cc")

        d.index = -1
        d.name = "001 foo"
        self.assertEqual(d.index, 1)
        d.name = "nope"
        self.assertEqual(d.index, 0)
        self.assertEqual(d.name, "000 aa")

    def testName2indexDeletion(self) -> None:
        lst: list[str] = ["000 aa"]
        d = DropdownHelper(MockDropdown(), lst, DropdownHelper.NameNotFoundHandling.SELECT_ANY)
        lst.clear()
        d.name2index()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)


class DrowpdownHelperUnselectTest(unittest.TestCase):
    def testIndexEmpty(self) -> None:
        d = DropdownHelper(MockDropdown(), [], DropdownHelper.NameNotFoundHandling.UNSELECT)
        d.ensure_index_bounds()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)

    def testAdding(self) -> None:
        lst: list[str] = []
        d = DropdownHelper(MockDropdown(), lst, DropdownHelper.NameNotFoundHandling.UNSELECT)
        lst.append("aa")
        d.ensure_index_bounds()
        self.assertEqual(d.index, -1)
        self.assertEqual(d.name, "")
        d.index = 10
        d.ensure_index_bounds()
        self.assertEqual(d.index, -1)
        self.assertEqual(d.name, "")
        lst.append("bb")
        d.ensure_index_bounds()
        self.assertEqual(d.index, -1)
        self.assertEqual(d.name, "")

    def testIndex2Name(self) -> None:
        lst: list[str] = ["0 aa", "bb", "cc"]
        d = DropdownHelper(MockDropdown(), lst, DropdownHelper.NameNotFoundHandling.UNSELECT)
        self.assertEqual(d.index, -1)
        self.assertEqual(d.name, "")
        d.index2name()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)
        d.index = 0
        d.index2name()
        self.assertEqual(d.name, "0 aa")
        self.assertEqual(d.index, 0)
        d.index = 10
        d.index2name()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)

    def testName2index(self) -> None:
        lst: list[str] = ["000 aa", "abc:bb", "2 cc"]
        d = DropdownHelper(MockDropdown(), lst, DropdownHelper.NameNotFoundHandling.UNSELECT)
        d.index = 10
        d.name2index()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)
        d.name = "001 foo"
        d.name2index()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)
        d.name = "2 cc"
        self.assertEqual(d.index, 2)
        self.assertEqual(d.name, "2 cc")

    def testName2indexDeletion(self) -> None:
        lst: list[str] = ["000 aa"]
        d = DropdownHelper(MockDropdown(), lst, DropdownHelper.NameNotFoundHandling.UNSELECT)
        self.assertEqual(d.index, -1)
        d.index = 0
        self.assertEqual(d.index, 0)
        lst.clear()
        d.ensure_index_bounds()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)


if __name__ == '__main__':
    unittest.main()
