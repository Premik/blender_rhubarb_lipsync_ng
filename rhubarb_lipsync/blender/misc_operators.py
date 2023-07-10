import logging

import bpy
from bpy.props import EnumProperty
from bpy.types import Context

from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.rhubarb.log_manager import logManager
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, ResultLogListProperties, ResultLogItemProperties

log = logging.getLogger(__name__)


class SetLogLevel(bpy.types.Operator):
    """Enable/disable more verbose logging to console"""

    bl_idname = "rhubarb.set_log_level"
    bl_label = "Log level"
    bl_options = {'UNDO', 'REGISTER'}

    level: EnumProperty(  # type: ignore
        name="Log Level",
        items=[
            (str(logging.FATAL), 'FATAL', ""),
            (str(logging.ERROR), 'ERROR', ""),
            (str(logging.WARNING), 'WARNING', ""),
            (str(logging.INFO), 'INFO', ""),
            (str(logging.DEBUG), 'DEBUG', ""),
            (str(logging.TRACE), 'TRACE', ""),
            (str(logging.NOTSET), 'DEFAULT', ""),
        ],
        default=str(logging.INFO),
    )

    def execute(self, context: Context) -> set[str]:
        level = int(self.level)
        logManager.set_level(level)
        prefs = RhubarbAddonPreferences.from_context(context)
        # Save to prefs so the same level can get recoveret on restart/register
        prefs.log_level = level

        self.report({'INFO'}, f"Set log level '{logManager.level2name(level)}' for {len(logManager.logs)} loggers")

        return {'FINISHED'}


class ShowResultLogDetails(bpy.types.Operator):
    """Bake the selected objects to nla tracks"""

    bl_idname = "rhubarb.show_result_log"
    bl_label = "Show result details"

    def draw(self, ctx: Context) -> None:
        rll: ResultLogListProperties = CaptureListProperties.from_context(ctx).last_resut_log
        box = self.layout.box()
        for _i in rll.items:
            log: ResultLogItemProperties = _i
            row = box.row()
            row = row.split(factor=0.3)
            row.label(text=log.trace)
            icon = 'ERROR'
            if log.level == "ERROR":
                row.alert = True
            else:
                box.alert = False
            if log.level == "INFO":
                icon = "INFO"
            row.label(text=log.msg, icon=icon)

    def invoke(self, context: Context, event: bpy.types.Event) -> set[int] | set[str]:
        return context.window_manager.invoke_props_dialog(self, width=1000)

    def execute(self, ctx: Context) -> set[str]:
        rll: ResultLogListProperties = CaptureListProperties.from_context(ctx).last_resut_log
        rll.items.clear()
        ui_utils.redraw_3dviews(ctx)
        return {'FINISHED'}
