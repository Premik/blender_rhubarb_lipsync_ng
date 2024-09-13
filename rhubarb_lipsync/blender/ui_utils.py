import logging
import pathlib
import traceback
from typing import Any, Callable, Iterator, Type

import bpy
import bpy.utils.previews
from bpy.types import Area, Context, UILayout, Window

log = logging.getLogger(__name__)

def addon_path() -> pathlib.Path:
    return pathlib.Path(__file__).parent.parent


def resources_path() -> pathlib.Path:
    return addon_path() / 'resources'


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
    assert props and property_name, f"Blank '{property_name}' or '{props}'"
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
    try:
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
    except Exception as e:
        msg = f"Unexpected error occured when validating operator: {e}"
        log.error(msg)
        log.debug(traceback.format_exc())
        cls.poll_message_set(msg)  # type: ignore
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
