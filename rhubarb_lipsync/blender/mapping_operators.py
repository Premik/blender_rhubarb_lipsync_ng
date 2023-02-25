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
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfos, MouthShapeInfo
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


class ShowCueInfoHelp(bpy.types.Operator):
    """Show a popup with cue type description."""

    bl_idname = "rhubarb.show_cueinfo_help"
    bl_label = "Cue type help"

    key: StringProperty("Key", description="The cue type key to show the help on.", default="")  # type:ignore

    @staticmethod
    def draw_popup(this: bpy.types.UIPopupMenu, key: str, context: Context) -> None:
        layout = this.layout
        msi: MouthShapeInfo = MouthShapeInfos[key].value

        # r = layout.row()

        # layout.label(text=msi.description)
        ui_utils.draw_error(layout, msi.description)

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, CaptureProperties.context_selection_validation)

    def execute(self, context: Context) -> set[str]:
        props = CaptureProperties.from_context(context)
        mporps: MappingList = props.mapping
        if not self.key:
            si = mporps.selected_item
            if not si:
                self.report(type={'ERROR'}, message=f"No cue key provided and no mapping item selected.")
                return {'CANCELLED'}
            self.key = si.key

        draw = lambda this, ctx: ShowCueInfoHelp.draw_popup(this, self.key, ctx)
        msi: MouthShapeInfo = MouthShapeInfos[self.key].value
        bpy.context.window_manager.popup_menu(draw, title=msi.short_dest, icon='INFO')

        return {'FINISHED'}
