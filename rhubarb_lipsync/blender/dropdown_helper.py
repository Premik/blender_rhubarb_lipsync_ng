import re
from enum import Enum
from typing import Sequence


class DropdownHelper:
    """Helper for building dropdowns for non-ID items of an collection. Item is referenced
    by index and a (search-)name. Index is further encoded as number prefix of the name separated by space.
    For example: `001 First item`.
    """

    numbered_item_re = re.compile(r"^(?:(?P<idx>\d+)\s+)?(?P<track_name>\S.*\S|\S)$")
    NameNotFoundHandling = Enum('NameNotFoundHandling', ['SELECT_ANY', 'UNSELECT'])

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
        return getattr(self.obj, 'index', -1)

    @index.setter
    def index(self, index: int) -> None:
        if self.index != index:
            setattr(self.obj, 'index', index)
            self.index2name()

    @property
    def name(self) -> str:
        return getattr(self.obj, 'name', "")

    @name.setter
    def name(self, n: str) -> None:
        if self.name != n:
            setattr(self.obj, 'name', n)
            self.name2index()

    @staticmethod
    def parse_name(numbered_item: str) -> tuple[int, str]:
        """Parses a numbered item and returns a tuple containing the index and track name part.
        For example '001 The item' => (1, ' The item')
        If the item doesn't match the pattern, returns (-1, "")
        """
        if not numbered_item:
            return (-1, "")
        m = DropdownHelper.numbered_item_re.search(numbered_item)
        if m is None:
            return (-1, "")

        groups = m.groupdict()
        idx = groups["idx"]
        track_name = groups["track_name"]

        if idx is None:
            idx = -1
        else:
            idx = int(idx)

        if track_name is None:
            track_name = ""

        return (idx, track_name)

    @property
    def index_from_name(self) -> str:
        return DropdownHelper.parse_name(self.name)[0]

    @property
    def track_name_from_name(self) -> str:
        return DropdownHelper.parse_name(self.name)[1]

    def is_track_name_match(self, index: int, track_name: str) -> bool:
        """Check if item at index has matching track name."""
        if index < 0 or index >= len(self.names):
            return False
        _, item_track_name = DropdownHelper.parse_name(self.names[index])
        return item_track_name == track_name

    def sync_from_items(self) -> None:
        """Sync index based on track name, trying to maintain position or adjust minimally. Used when tracks changes (add/delete..)"""
        if len(self.names) == 0:  # No more track left
            self.index = -1
            self.name = ""
            return

        current_track_name = self.track_name_from_name
        if not current_track_name:
            self.ensure_index_bounds()
            self.index2name()
            return

        # Check if current index still matches
        current_index = self.index
        if self.is_track_name_match(current_index, current_track_name):
            self.index2name()  # Just update name format
            return

        # Try adjacent indices first (handle insertion/deletion)
        if self.is_track_name_match(current_index + 1, current_track_name):
            self.index = current_index + 1
            self.index2name()
            return

        if self.is_track_name_match(current_index - 1, current_track_name):
            self.index = current_index - 1
            self.index2name()
            return

        # Scan all items for matching track name
        for i, name in enumerate(self.names):
            _, item_track_name = DropdownHelper.parse_name(name)
            if item_track_name == current_track_name:
                self.index = i
                self.index2name()
                return

        # No match found, apply nameNotFoundHandling
        if self.nameNotFoundHandling == DropdownHelper.NameNotFoundHandling.SELECT_ANY:
            self.ensure_index_bounds()
        else:
            self.index = -1
            self.name = ""

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
        """Changes the index property based on the name property. Takes index from the name prefix"""
        index = self.index_from_name
        index = self.index_within_bounds(index)
        if self.index != index:
            self.index = index  # Change
        self.index2name()  # Sync name too

    def index2name(self) -> None:
        """"""
        self.ensure_index_bounds()
        if self.index >= 0:
            self.name = self.names[self.index]

    def select_last(self) -> None:
        l = len(self.names)
        self.index = l - 1
