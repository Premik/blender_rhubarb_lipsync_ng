import bpy
from bpy.types import Context, Window, Area, UILayout
from typing import Any, Iterator
from rhubarb_lipsync.blender.properties import CaptureProperties


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


def context_selection_validation(ctx: Context) -> str:
    if not ctx.object:
        return "No active object selected"
    if not CaptureProperties.from_context(ctx):
        return "'rhubarb_lipsync' not found on the active object"
    return ""


def assert_op_ret(ret: set[str]):
    assert 'FINISHED' in ret, f"Operation execution failed with {ret} code"


def draw_expandable_header(props: Any, property_name: str, label: str, layout: UILayout) -> bool:
    """Draws a checkbox which looks like collapsable sub-panel's header.
    Expanded/collapsed state is driven by the provided property.
    Returns the exapnded status. Inspired by GameRigtTool plugin"""
    assert props and property_name
    expanded = getattr(props, property_name)
    if expanded:
        icon = "TRIA_DOWN"
    else:
        icon = "TRIA_RIGHT"

    row = layout.row(align=True)
    row.alignment = "LEFT"
    row.prop(props, property_name, text=label, emboss=False, icon=icon)

    return expanded
