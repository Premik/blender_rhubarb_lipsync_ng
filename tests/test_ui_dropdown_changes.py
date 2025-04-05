import unittest

from rhubarb_lipsync.blender.dropdown_helper import DropdownHelper
from test_dropdown_selections import MockDropdown

# def setUpModule():
#    rhubarb_lipsync.register()  # Simulate blender register call


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
        self.assertEqual(d.item_name_from_name, "item2")

        # Change list: insert new item before item2
        d.names = ["0 item1", "1 newitem", "2 item2", "3 item3"]

        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.MOVED_TO)
        self.assertEqual(new_index, 2)

    def test_detect_moved_left(self) -> None:
        d = self.create_dropdown(["0 item1", "1 newitem", "2 item2", "3 item3"])
        d.index = 2
        self.assertEqual(d.item_name_from_name, "item2")

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

    def test_detect_renamed(self) -> None:
        mock = MockDropdown()

        d = DropdownHelper(mock, ["0 item1", "1 item2", "2 item3"], DropdownHelper.NameNotFoundHandling.UNSELECT)
        d.index = 1
        d.last_length = 3
        self.assertEqual(d.item_name_from_name, "item2")

        # Keep same length but rename item at index 1
        d.names = ["0 item1", "1 renamed_item", "2 item3"]
        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.RENAMED)
        self.assertEqual(new_index, 1)  # Same index but renamed

    def test_detect_renamed_with_multiple_changes(self) -> None:
        mock = MockDropdown()

        d = DropdownHelper(mock, ["0 item1", "1 item2", "2 item3"], DropdownHelper.NameNotFoundHandling.UNSELECT)
        d.last_length = 3
        d.index = 1

        # Change other items but keep same length and rename item at index 1
        d.names = ["0 changed1", "1 renamed_item", "2 changed3"]

        # Detect changes
        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.RENAMED)
        self.assertEqual(new_index, 1)


if __name__ == '__main__':
    unittest.main()
