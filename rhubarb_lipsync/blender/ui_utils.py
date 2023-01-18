import bpy
from bpy.types import Context, Window, Area
from typing import Iterator
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
