import pathlib
import re
import traceback
from enum import Enum
from typing import Any, Callable, Iterator, Sequence, Type

import bpy
import bpy.utils.previews
from bpy.types import Area, Context, UILayout, Window


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
    def get_icon(key: str) -> int:
        if IconsManager._previews is None:
            IconsManager._previews = bpy.utils.previews.new()
        prew = IconsManager._previews
        if key not in IconsManager._loaded:
            IconsManager._loaded.add(key)
            fn = key
            if not pathlib.Path(key).suffix:
                fn = f"{key}.png"  # .png default extension
            prew.load(key, str(resources_path() / fn), 'IMAGE')
        return prew[key].icon_id

    @staticmethod
    def get_image(image_name: str) -> tuple[bpy.types.Image, bpy.types.Texture]:
        """Loads an image into Blender's data blocks."""
        if not image_name.endswith(".png"):
            image_name = f"{image_name}.png"
        image_path = resources_path() / image_name
        # if not image_path.exists():
        #     raise RuntimeError(f"Image not found: {image_path}")
        img = bpy.data.images.load(str(image_path), check_existing=True)
        # img.preview_ensure()
        # Create a new texture and assign the loaded image to it
        text_name = image_name
        if not text_name in bpy.data.textures.keys():
            tex = bpy.data.textures.new(name=image_name, type='IMAGE')
            tex.extension = 'EXTEND'
            tex.image = img
        else:
            tex = bpy.data.textures[text_name]

        return img, tex

    @staticmethod
    def logo_icon() -> int:
        return IconsManager.get_icon('rhubarb64x64')
        # return IconsManager.get('1.dat')

    @staticmethod
    def placement_help_image() -> tuple[bpy.types.Image, bpy.types.Texture]:
        return IconsManager.get_image('placementSettings')
        # return IconsManager.get('1.dat')

    @staticmethod
    def cue_icon(key: str) -> int:
        return IconsManager.get_icon(f"lisa-{key}")


def addons_path() -> pathlib.Path:
    ap = bpy.utils.user_resource('SCRIPTS', path="addons")
    if not ap:
        return pathlib.Path()
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
    # TODO This could probably be done better using columns layout
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
    """Helper method to show a validation error of an operator to user in a popup."""
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


def redraw_3dviews(ctx: Context) -> None:
    if ctx.area:
        ctx.area.tag_redraw()
    for area in ctx.screen and ctx.screen.areas or []:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def set_panel_category(panel, category: str) -> None:
    """Change the bl_category of the Panel by re-registering the class. This would rename the tab the panel is shown in."""
    try:
        if "bl_rna" in panel.__dict__:  # Is the class registered?
            bpy.utils.unregister_class(panel)  # Unregister first if so
        panel.bl_category = category
        # label_with_prefix:str=panel.bl_label.split(": ", 1)
        # panel.bl_label=f"{category}{}"
        bpy.utils.register_class(panel)
    except:
        print("Failed to change panel category")
        traceback.print_exc()


def len_limited(iterator: Iterator, max_count=1000) -> int:
    """Count the number of items of an iterator but would break if the limit is reached."""
    count = 0
    for _ in iterator:
        count += 1
        if count >= max_count:
            break
    return count


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
        index = DropdownHelper.index_from_name(self.name)
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
