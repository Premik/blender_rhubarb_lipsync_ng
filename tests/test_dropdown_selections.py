import unittest

from rhubarb_lipsync.blender.dropdown_helper import DropdownHelper


class MockDropdown:
    def __init__(self) -> None:
        self.index = -1
        self.name = ""
        self.last_length = 0

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
    #     self.assertEqual(d.item_name_from_name, "bb")

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


if __name__ == '__main__':
    unittest.main()
