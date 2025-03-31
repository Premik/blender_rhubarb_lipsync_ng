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
    def create_dropdown(self, items: list[str], handling_mode=DropdownHelper.NameNotFoundHandling.SELECT_ANY) -> DropdownHelper:
        return DropdownHelper(MockDropdown(), items, handling_mode)

    def testIndexEmpty(self) -> None:
        d = self.create_dropdown([])
        d.ensure_index_bounds()
        self.assertEqual(len(d.names), 0)
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)

    def testAddingToEnd(self) -> None:
        lst: list[str] = []
        d = self.create_dropdown(lst)
        lst.append("aa")
        d.ensure_index_bounds()
        self.assertEqual(d.index, 0, "Originally invalid index didn't change to the first item")
        lst.append("bb")
        d.ensure_index_bounds()
        self.assertEqual(d.index, 0)
        self.assertEqual(d.name, "aa")

    def testAddingToBegening(self) -> None:
        lst: list[str] = ["aa"]
        d = self.create_dropdown(lst)
        d.index = 0
        lst.insert(0, "zz")
        d.sync_from_items()
        self.assertEqual(d.index, 1)
        self.assertEqual(d.name, "aa")

    def testIndex2Name(self) -> None:
        lst: list[str] = ["0 aa", "1 bb", "2 cc"]
        d = self.create_dropdown(lst)
        d.ensure_index_bounds()
        self.assertEqual(d.index, 0)
        self.assertEqual(d.name, "0 aa")
        d.index = 10
        d.index2name()
        self.assertEqual(d.name, "2 cc")

    @unittest.skip("For SELECT_ANY, no unselecting possible currently")
    def testUnselecting(self) -> None:
        d = self.create_dropdown(["aa", "bb", "cc"])
        d.index = -1
        d.index2name()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)

    def testName2index(self) -> None:
        d = self.create_dropdown(["000 aa", "001 bb", "2 cc"])
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
        d = self.create_dropdown(lst)
        lst.clear()
        d.name2index()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)


class DrowpdownHelperUnselectTest(unittest.TestCase):
    def create_dropdown(self, items: list[str]) -> DropdownHelper:
        return DropdownHelper(MockDropdown(), items, DropdownHelper.NameNotFoundHandling.UNSELECT)

    def testIndexEmpty(self) -> None:
        d = self.create_dropdown([])
        d.ensure_index_bounds()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)

    def testAdding(self) -> None:
        lst: list[str] = []
        d = self.create_dropdown(lst)
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

    # def testRename(self) -> None:
    #     lst: list[str] = ["0 aa", "1 bb", "2 cc"]
    #     d = self.create_dropdown(lst)
    #     d.index = 1
    #     d.ensure_index_bounds()
    #     self.assertEqual(d.index_from_name, 1)
    #     self.assertEqual(d.track_name_from_name, "bb")

    def testIndex2Name(self) -> None:
        d = self.create_dropdown(["0 aa", "bb", "cc"])
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
        d = self.create_dropdown(["000 aa", "abc:bb", "2 cc"])
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
        d = self.create_dropdown(lst)
        self.assertEqual(d.index, -1)
        d.index = 0
        self.assertEqual(d.index, 0)
        lst.clear()
        d.ensure_index_bounds()
        self.assertEqual(d.name, "")
        self.assertEqual(d.index, -1)


class DropdownHelperChangeDetectionTest(unittest.TestCase):
    def create_dropdown(self, items: list[str]) -> DropdownHelper:
        mock = MockDropdown()
        ret = DropdownHelper(mock, items, DropdownHelper.NameNotFoundHandling.UNSELECT)
        return ret

    def test_detect_empty_list(self) -> None:
        d = self.create_dropdown([])
        status, _ = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.UNCHANGED)

    def test_removed_last(self) -> None:
        lst: list[str] = ["0 aa"]
        d = self.create_dropdown(lst)
        d.index = 0
        lst.clear()
        status, _ = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.REMOVED)

    def test_detect_unchanged(self) -> None:
        d = self.create_dropdown(["0 item1", "1 item2", "2 item3"])
        d.index = 1
        status, _ = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.UNCHANGED)

    def test_detect_moved_right(self) -> None:
        d = self.create_dropdown(["0 item1", "1 item2", "2 item3"])
        d.index = 1
        self.assertEqual(d.track_name_from_name, "item2")

        # Change list: insert new item before item2
        d.names = ["0 item1", "1 newitem", "2 item2", "3 item3"]

        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.MOVED_TO)
        self.assertEqual(new_index, 2)

    def test_detect_moved_left(self) -> None:
        d = self.create_dropdown(["0 item1", "1 newitem", "2 item2", "3 item3"])
        d.index = 2
        self.assertEqual(d.track_name_from_name, "item2")

        d.names = ["0 item1", "1 item2", "2 item3"]

        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.MOVED_TO)
        self.assertEqual(new_index, 1)

    def test_detect_moved_distant(self) -> None:
        d = self.create_dropdown(["0 item1", "1 item2", "2 item3"])
        d.index = 1

        # Change list drastically
        d.names = ["0 item1", "1 newitem", "2 newitem2", "3 newitem3", "4 item2", "5 item3"]

        # Detect changes
        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.MOVED_TO)
        self.assertEqual(new_index, 4)  # item2 moved to index 4

    def test_detect_removed(self) -> None:
        d = self.create_dropdown(["0 item1", "2 item2", "3 item3"])
        d.index = 1
        d.names = ["1 item1", "2 item3"]  # Remove item2 from the list

        status, _ = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.REMOVED)


if __name__ == '__main__':
    unittest.main()
