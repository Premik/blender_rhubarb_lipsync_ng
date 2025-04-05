import logging
import re
from enum import Enum
from typing import Sequence, Tuple

log = logging.getLogger(__name__)


class DropdownHelper:
    """Helper for building dropdowns for non-ID items of an collection. Item is referenced
    by index and a (search) name. Index is further encoded as number prefix of the name separated by space.
    For example: `001 First item`.
    """

    numbered_item_re = re.compile(r"^(?:(?P<idx>\d+)\s+)?(?P<item_name>\S.*\S|\S)$")
    NameNotFoundHandling = Enum('NameNotFoundHandling', ['SELECT_ANY', 'UNSELECT'])
    ChangeStatus = Enum('ChangeStatus', ['UNCHANGED', 'MOVED_TO', 'REMOVED', 'RENAMED'])

    def __init__(self, dropdown, names: Sequence[str], nameNotFoundHandling=NameNotFoundHandling.SELECT_ANY) -> None:
        self.obj = dropdown
        self.names = names
        self.nameNotFoundHandling = nameNotFoundHandling
        # if nameNotFoundHandling == DropdownHelper.NameNotFoundHandling.UNSELECT:
        # self.index = -1
        # else
        # self.ensure_index_bounds()

    @property
    def index(self) -> int:
        """Currently selected index."""
        return getattr(self.obj, 'index', -1)

    @index.setter
    def index(self, index: int) -> None:
        if self.index != index:
            setattr(self.obj, 'index', index)
            self.index2name()

    @property
    def name(self) -> str:
        """Currently selected full name (e.g., '001 Item Name')."""
        return getattr(self.obj, 'name', "")

    @name.setter
    def name(self, n: str) -> None:
        if self.name != n:
            setattr(self.obj, 'name', n)
            self.name2index()

    @property
    def last_length(self) -> int:
        """Last known length of the items collection."""
        return getattr(self.obj, 'last_length', -1)

    @last_length.setter
    def last_length(self, length: int) -> None:
        if hasattr(self.obj, 'last_length'):
            setattr(self.obj, 'last_length', length)

    @property
    def last_length_supported(self) -> bool:
        """Check if the underlying object supports storing the last length."""
        return self.last_length >= 0

    @staticmethod
    def parse_name(numbered_item: str) -> tuple[int, str]:
        """Parses a numbered item and returns a tuple containing the index and item name part.
        For example '001 The item' => (1, ' The item')
        If the item doesn't match the pattern, returns (-1, "")
        """
        if not numbered_item:
            return (-1, "")
        m = DropdownHelper.numbered_item_re.search(numbered_item)
        if m is None:
            return (-1, "")

        groups = m.groupdict()
        idx_str = groups.get("idx")  # Use .get for safety
        item_name = groups.get("item_name", "")  # Default to empty string

        if idx_str is None:
            idx = -1
        else:
            try:
                idx = int(idx_str)
            except ValueError:
                idx = -1  # Handle potential non-integer index string

        return (idx, item_name)

    @property
    def index_from_name(self) -> int:
        """Gets the index encoded in the item name prefix. Returns -1 if not found/invalid."""
        return DropdownHelper.parse_name(self.name)[0]

    @property
    def item_name_from_name(self) -> str:
        """Gets the underlying item name (without the encoded index prefix)."""
        return DropdownHelper.parse_name(self.name)[1]

    def item_name_match(self, index: int, item_name_to_match: str) -> bool:
        """Check if the item at the given index in the current list has a matching item name part."""
        if not (0 <= index < len(self.names)):
            return False
        _, current_item_name = DropdownHelper.parse_name(self.names[index])
        return current_item_name == item_name_to_match

    def detect_item_changes(self) -> Tuple[ChangeStatus, int]:
        """Detects changes in the items collection relative to the current selection (`self.index`, `self.name`).

        Returns: Tuple (ChangeStatus, New/Current index)
        """

        current_length = len(self.names)
        previous_length = self.last_length
        if self.last_length_supported:
            self.last_length = current_length
        index = self.index
        item_name = self.item_name_from_name
        if current_length == 0:
            if self.index < 0:  # Nothing was selected, so no change
                return (DropdownHelper.ChangeStatus.UNCHANGED, self.index)
            else:  # Something was selected so it means it was removed
                return (DropdownHelper.ChangeStatus.REMOVED, -1)

        # Something was selected (index >= 0)
        # Use the item_name derived from the stored self.name property
        # if not item_name: # If the stored name was invalid or empty
        #     # Treat as if the item was removed, force selection/unselection based on policy
        #     if self.nameNotFoundHandling == DropdownHelper.NameNotFoundHandling.SELECT_ANY:
        #         new_index = self.index_within_bounds(0) # Try selecting first item
        #         return (DropdownHelper.ChangeStatus.MOVED_TO, new_index)
        #     else:
        #         return (DropdownHelper.ChangeStatus.REMOVED, -1)

        # Is item still at the same index with the same name?
        if self.item_name_match(index, item_name):
            return (DropdownHelper.ChangeStatus.UNCHANGED, index)

        # Try adjacent indices first (handle single insertion/deletion, optimization)
        if self.item_name_match(index + 1, item_name):
            return (DropdownHelper.ChangeStatus.MOVED_TO, index + 1)

        if self.item_name_match(index - 1, item_name):
            return (DropdownHelper.ChangeStatus.MOVED_TO, index - 1)

        # Scan all items for matching item name
        for i, name in enumerate(self.names):
            _, current_item_name = DropdownHelper.parse_name(name)
            if current_item_name == item_name:
                return (DropdownHelper.ChangeStatus.MOVED_TO, i)

        # No item with matching name not found. Could be REMOVED or RENAMED. Use last_length to deduce.
        if self.last_length_supported and previous_length == current_length and 0 <= index < current_length:
            # Length is the same, index is still valid, and name didn't match anywhere.
            # Assume item at `index` was renamed in place.
            return (DropdownHelper.ChangeStatus.RENAMED, index)
        if self.nameNotFoundHandling == DropdownHelper.NameNotFoundHandling.SELECT_ANY:
            index = self.index_within_bounds()
            return (DropdownHelper.ChangeStatus.MOVED_TO, index)
        else:
            return (DropdownHelper.ChangeStatus.REMOVED, self.index_within_bounds(-1))

    def sync_from_items(self) -> None:
        """Sync index based on item name, trying to maintain position or adjust minimally. Used when items changes (add/delete..)"""
        status, new_index = self.detect_item_changes()
        log.trace(f"Dropdown change detected: {status}@{new_index} on {self.obj}")
        if status == DropdownHelper.ChangeStatus.UNCHANGED:
            return
        if status == DropdownHelper.ChangeStatus.MOVED_TO:
            self.index = new_index
            return
        if status == DropdownHelper.ChangeStatus.RENAMED:
            self.index2name()  # Update the name with new one from the same current index
            return
        # Removed
        if self.nameNotFoundHandling == DropdownHelper.NameNotFoundHandling.SELECT_ANY:
            new_index = self.index_within_bounds(max(0, self.index - 1))  # Try to select a nearby item if available
            self.index = new_index
        else:  # Unselect
            self.index = -1

    def index_within_bounds(self, index=None) -> int:
        """Returns index bounded to the names length without changing the `index` attr.
        Returns -1 when the list is empty"""
        l = len(self.names)
        if l == 0:
            return -1  # Empty list
        if index is None:
            index = self.index
        if index >= l:  # After the last
            if self.nameNotFoundHandling == DropdownHelper.NameNotFoundHandling.SELECT_ANY:
                index = l - 1  # Select last
            else:
                index = -1  # Unselect

        if index < 0:  # Befor the first (unselected)
            if self.nameNotFoundHandling == DropdownHelper.NameNotFoundHandling.SELECT_ANY:
                index = 0  # Select first
            else:
                index = -1  # Keep unselected, make sure not <-1
        return index

    def ensure_index_bounds(self) -> None:
        """Changes the `index` attr to be within the `items` bounds."""
        new = self.index_within_bounds()
        if self.index != new:
            self.index = new
            self.index2name()
        if self.index < 0:
            if self.name:
                # index_from_name = DropdownHelper.index_from_name(self.name)
                self.name = ""
            return

    def name2index(self) -> None:
        """Changes the index property based on the name property. Takes index from the name prefix.
        This is used when a new search-name is selected from dropdown
        """
        index = self.index_from_name
        index = self.index_within_bounds(index)
        self.index = index
        # self.index2name()  # Sync name too

    def index2name(self) -> None:
        self.ensure_index_bounds()
        if self.index >= 0:
            self.name = self.names[self.index]
        else:
            self.name = ""

    def select_last(self) -> None:
        l = len(self.names)
        self.index = l - 1
