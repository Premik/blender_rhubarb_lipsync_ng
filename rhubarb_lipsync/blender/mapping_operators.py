import logging
from functools import cached_property
from types import ModuleType
from typing import Dict, List, Optional, cast
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty, BoolProperty
from bpy.types import Context


from rhubarb_lipsync.blender.properties import CaptureProperties, MappingList
from rhubarb_lipsync.rhubarb.log_manager import logManager
import rhubarb_lipsync.blender.ui_utils as ui_utils
import traceback

log = logging.getLogger(__name__)


class BuildCueInfoUIList(bpy.types.Operator):
    """Populate the cue mapping list with the know cue types."""

    bl_idname = "rhubarb.build_cueinfo_uilist"
    bl_label = "Initialize mapping list"

    # @classmethod
    # def disabled_reason(cls, context: Context, limit=0) -> str:
    #    props = CaptureProperties.from_context(context)
    #    mporps: MappingList = props.mapping
    #    if len(mporps.items) > 0:
    #        return f"Cue mapping info is already populated"
    #    return ""

    # @classmethod
    # def poll(cls, context: Context) -> bool:
    #    return ui_utils.validation_poll(cls, context)

    def execute(self, context: Context) -> set[str]:
        props = CaptureProperties.from_context(context)
        mporps: MappingList = props.mapping
        mporps.items.clear()
        mporps.build_items()

        return {'FINISHED'}
