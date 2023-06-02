from enum import Enum
import pathlib
import re
from typing import Any, Callable, Iterator, Type, Sequence

import bpy
from bpy.types import Area, Context, Sound, SoundSequence, UILayout, Window


class IconsManager:
    _previews: bpy.utils.previews.ImagePreviewCollection = None
    _loaded: set[str] = set()

    @staticmethod
    def unregister() -> None:
        if IconsManager._previews:
            IconsManager._previews.close()
            # bpy.utils.previews.remove(IconsManager._previews)
            IconsManager._previews = None
            IconsManager._loaded = set()

    @staticmethod
    def get(key: str) -> int:
        if IconsManager._previews is None:
            IconsManager._previews = bpy.utils.previews.new()
        prew = IconsManager._previews
        if not key in IconsManager._loaded:
            IconsManager._loaded.add(key)
            fn = key
            if not pathlib.Path(key).suffix:
                fn = f"{key}.png"  # .png default extension
            prew.load(key, str(resources_path() / fn), 'IMAGE')
        return prew[key].icon_id

    @staticmethod
    def logo_icon() -> int:
        return IconsManager.get('rhubarb64x64')
        # return IconsManager.get('1.dat')

    @staticmethod
    def cue_image(key: str) -> int:
        return IconsManager.get(f"lisa-{key}")

    @staticmethod
    def cue_icon(key: str) -> int:
        return IconsManager.get(f"lisa-{key}")


def addons_path() -> pathlib.Path:
    ap = bpy.utils.user_resource('SCRIPTS', path="addons")
    return pathlib.Path(ap)


def resources_path() -> pathlib.Path:
    return addons_path() / 'rhubarb_lipsync' / 'resources'


def find_areas_by_type(context: Context, area_type: str) -> Iterator[tuple[Window, Area]]:
    assert context
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != area_type:
                continue
            yield (window, area)


def get_sequencer_context(context: Context) -> dict:
    """Context needed for sequencer ops (visible sequencer is needed)"""
    areas = list(find_areas_by_type(context, 'SEQUENCE_EDITOR'))
    if not areas:
        return {}
    (window, area) = areas[0]
    return {
        "window": window,
        "screen": window.screen,
        "area": area,
        "scene": context.scene,
    }


def assert_op_ret(ret: set[str]) -> None:
    assert 'FINISHED' in ret, f"Operation execution failed with {ret} code"


def draw_expandable_header(props: Any, property_name: str, label: str, layout: UILayout, errors=False) -> bool:
    """Draws a checkbox which looks like collapsable sub-panel's header.
    Expanded/collapsed state is driven by the provided property.
    Returns the expanded status. Inspired by GameRigtTool plugin"""
    assert props and property_name
    row = layout.row(align=True)
    row.alignment = "LEFT"

    expanded = getattr(props, property_name)
    if expanded:
        # icon = 'TRIA_DOWN'
        icon = 'DISCLOSURE_TRI_DOWN'
    else:
        # icon = 'TRIA_RIGHT'
        icon = 'DISCLOSURE_TRI_RIGHT'
        if errors:
            row.alert = True
            icon = "ERROR"

    row.prop(props, property_name, text=label, emboss=False, icon=icon)

    return expanded


def draw_prop_with_label(props: Any, property_name: str, label, layout: UILayout) -> None:
    col = layout.column()
    split = col.split(factor=0.229)
    split.alignment = 'LEFT'
    split.label(text=label)
    split.prop(props, property_name, text="")


def draw_error(layout, msg: str) -> None:
    box = layout.box()
    box.alert = True
    lines = msg.splitlines()
    if not lines:
        lines = [""]
    if len(lines) == 1:  # Single line
        box.label(text=msg, icon="ERROR")
        return
    # Multiline
    box.label(text="", icon="ERROR")
    for l in lines:
        box.label(text=l, icon="BLANK1")


def to_relative_path(blender_path: str) -> str:
    if not blender_path:
        return ""
    try:  # Can fail on windows
        return bpy.path.relpath(blender_path)
    except ValueError:
        return blender_path  # Keep unchanged


def to_abs_path(blender_path: str) -> str:
    if not blender_path:
        return ""
    return bpy.path.abspath(blender_path)


def validation_poll(cls: Type, context: Context, disabled_reason: Callable[[Context], str] = None) -> bool:
    assert cls
    if not disabled_reason:  # Locate the 'disabled_reason' as the validation fn if no one is provided
        assert hasattr(cls, 'disabled_reason'), f"No validation function provided and the {cls} has no 'disabled_reason' class method"
        disabled_reason = cls.disabled_reason
    ret = disabled_reason(context)
    if not ret:  # No validation errors
        return True
    # Following is not a class method per doc. But seems to work like it
    cls.poll_message_set(ret)  # type: ignore
    return False


def func_fqname(fn: Callable) -> str:
    """Fully qualified function name. Including module name"""
    return f"{fn.__module__}/{fn.__qualname__}"


def remove_handler(handlers: list[Callable], fn: Callable) -> bool:
    """Remove function(s) from the handler list. Returns true if anything was removed"""
    fqfn = func_fqname(fn)
    remove = None
    try:
        remove = next((f for f in handlers if func_fqname(f) == fqfn))
        handlers.remove(remove)
        remove_handler(handlers, fn)
        return True
    except StopIteration:
        return False


class DropdownHelper:
    """Helper for building dropdowns for non-ID items of an collection. Item is referenced
    by index and a (search-)name. Index is further encoded as number prefix of the name separated by space.
    For example: `001 First item`.
    """

    numbered_item_re = re.compile(r"^(?P<idx>\d+)\s.*")
    NameNotFoundHandling = Enum('NameNotFoundHandling', ['SELECT_ANY', 'UNSELECT'])

    def __init__(self, dropdown, names: Sequence[str], nameNotFoundHandling=NameNotFoundHandling.SELECT_ANY) -> None:
        self.obj = dropdown
        self.names = names
        self.nameNotFoundHandling = nameNotFoundHandling
        if nameNotFoundHandling == DropdownHelper.NameNotFoundHandling.UNSELECT:
            self.index = -1
        else:
            self.ensure_index_bounds()

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
    def index_from_name(numbered_item: str) -> int:
        """Returns an index of a numbered item. Or -1 when not matching the pattern.
        For example '001 The item'  => 1
        """
        if not numbered_item:
            return -1
        m = DropdownHelper.numbered_item_re.search(numbered_item)
        if m is None:
            return -1
        idx = m.groupdict()["idx"]
        if idx is None:
            return -1
        return int(idx)

    def index_within_bounds(self, index=None) -> int:
        """Returns index bounded to the names length without changing the `index` attr.
        Returns -1 when the list is empty"""
        l = len(self.names)
        if l == 0:
            return -1  # Empty list
        if index == None:
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
                self.name = ""
            return

    def name2index(self) -> None:
        """Changes the index property based on the name property. Takes index from the name prefix"""
        index = DropdownHelper.index_from_name(self.name)
        index = self.index_within_bounds(index)
        if self.index == index:
            return  # Same index is already selected, ignore
        self.index = index  # Change
        self.index2name()  # Sync name too

    def index2name(self) -> None:
        """"""
        self.ensure_index_bounds()
        if self.index >= 0:
            self.name = self.names[self.index]
