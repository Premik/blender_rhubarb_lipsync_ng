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

    def create_dropdown_and_select(self, items: list[str], index: int) -> DropdownHelper:
        ret = self.create_dropdown(items)
        ret.index = index
        return ret

    def test_detect_empty_list(self) -> None:
        d = self.create_dropdown([])
        status, _ = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.UNCHANGED)

    def test_removed_last(self) -> None:
        lst: list[str] = ["0 aa"]
        d = self.create_dropdown_and_select(lst, 0)
        lst.clear()
        status, _ = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.REMOVED)

    def test_detect_unchanged(self) -> None:
        d = self.create_dropdown_and_select(["0 item1", "1 item2", "2 item3"], 1)
        status, _ = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.UNCHANGED)

    def test_detect_moved_right(self) -> None:
        d = self.create_dropdown_and_select(["0 item1", "1 item2", "2 item3"], 1)
        self.assertEqual(d.item_name_from_name, "item2")

        # Change list: insert new item before item2
        d.names = ["0 item1", "1 newitem", "2 item2", "3 item3"]

        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.MOVED_TO)
        self.assertEqual(new_index, 2)

    def test_detect_moved_left(self) -> None:
        d = self.create_dropdown_and_select(["0 item1", "1 newitem", "2 item2", "3 item3"], 2)
        self.assertEqual(d.item_name_from_name, "item2")

        d.names = ["0 item1", "1 item2", "2 item3"]

        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.MOVED_TO)
        self.assertEqual(new_index, 1)

    def test_detect_swap(self) -> None:
        orig_items = ["0 item1", "1 item2", "2 other"]
        new_items = ["0 item1", "1 other", "2 item2"]
        d = self.create_dropdown_and_select(orig_items, 0)
        d.names = new_items
        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.UNCHANGED)

        d = self.create_dropdown_and_select(orig_items, 1)
        d.names = new_items
        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.MOVED_TO)
        self.assertEqual(new_index, 2)

        d = self.create_dropdown_and_select(orig_items, 2)
        d.names = new_items
        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.MOVED_TO)
        self.assertEqual(new_index, 1)

    def test_detect_moved_distant(self) -> None:
        d = self.create_dropdown_and_select(["0 item1", "1 item2", "2 item3"], 1)

        # Change list drastically
        d.names = ["0 item1", "1 newitem", "2 newitem2", "3 newitem3", "4 item2", "5 item3"]

        # Detect changes
        status, new_index = d.detect_item_changes()
        self.assertEqual(status, DropdownHelper.ChangeStatus.MOVED_TO)
        self.assertEqual(new_index, 4)  # item2 moved to index 4

    def test_detect_removed(self) -> None:
        d = self.create_dropdown_and_select(["0 item1", "1 item2", "2 item3"], 1)
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


class DropdownHelperSyncTest(unittest.TestCase):
    def create_dropdown(self, items: list[str], handling_mode=DropdownHelper.NameNotFoundHandling.SELECT_ANY) -> DropdownHelper:
        mock = MockDropdown()
        ret = DropdownHelper(mock, items, handling_mode)
        return ret

    def test_sync_unchanged(self) -> None:
        """Test that sync does nothing when items are unchanged"""
        d = self.create_dropdown(["0 item1", "1 item2", "2 item3"])
        d.index = 1
        original_index = d.index
        original_name = d.name

        d.sync_from_items()

        self.assertEqual(d.index, original_index)
        self.assertEqual(d.name, original_name)

    def test_sync_item_moved_down(self) -> None:
        """Test that sync updates index when item is moved down"""
        d = self.create_dropdown(["0 item1", "1 item2", "2 item3"])
        d.index = 1

        # Change list: insert new item before item2
        d.names = ["0 item1", "1 newitem", "2 item2", "3 item3"]

        d.sync_from_items()

        self.assertEqual(d.index, 2)  # Should find item2 at new position
        self.assertEqual(d.item_name_from_name, "item2")

    def test_sync_item_moved_up(self) -> None:
        """Test that sync updates index when item is moved to the up"""
        d = self.create_dropdown(["0 item1", "1 item2", "2 item3"])
        d.index = 2

        # Change list: remove item2
        d.names = ["0 item1", "1 item3"]

        d.sync_from_items()

        self.assertEqual(d.index, 1)  # Should find item3 at new position
        self.assertEqual(d.item_name_from_name, "item3")

    def test_sync_item_renamed(self) -> None:
        """Test that sync handles renamed items"""
        d = self.create_dropdown(["0 item1", "1 item2", "2 item3"])
        d.index = 1
        d.last_length = 3  # Explicitly set last_length to enable rename detection

        # Change list: rename item2 to modified_item
        d.names = ["0 item1", "1 modified_item", "2 item3"]

        d.sync_from_items()

        # Index should stay the same, but name should be updated
        self.assertEqual(d.index, 1)
        self.assertEqual(d.item_name_from_name, "modified_item")

    def test_sync_item_removed_unselect(self) -> None:
        """Test that sync unselects when current item is removed with UNSELECT policy"""
        d = self.create_dropdown(["0 item1", "1 item2", "2 item3"], DropdownHelper.NameNotFoundHandling.UNSELECT)
        d.index = 1

        # Change list: remove item2
        d.names = ["0 item1", "1 item3"]

        d.sync_from_items()

        # Should unselect (index = -1)
        self.assertEqual(d.index, -1)

    def test_sync_all_items_removed_select_any(self) -> None:
        """Test that sync handles when all items are removed with SELECT_ANY policy"""
        d = self.create_dropdown(["0 item1", "1 item2"])
        d.index = 0

        # Change list: remove all items
        d.names = []

        d.sync_from_items()

        # Should unselect even with SELECT_ANY since there's nothing to select
        self.assertEqual(d.index, -1)

    def test_sync_new_items_added_when_unselected(self) -> None:
        """Test that sync maintains unselected state when new items are added"""
        d = self.create_dropdown([], DropdownHelper.NameNotFoundHandling.SELECT_ANY)
        d.index = -1  # Explicitly unselected

        # Add new items
        d.names = ["0 item1", "1 item2"]

        d.sync_from_items()

        # First item should get selected automatically
        self.assertEqual(d.index, 0)


if __name__ == '__main__':
    unittest.main()
