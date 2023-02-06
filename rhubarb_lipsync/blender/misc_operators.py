import bpy

from typing import Optional, List, Dict, cast
from types import ModuleType
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, IntProperty, EnumProperty
from bpy.types import Context
import rhubarb_lipsync.blender.auto_load
import logging
from functools import cached_property
from rhubarb_lipsync.rhubarb.log_manager import logManager
from rhubarb_lipsync.blender.properties import RhubarbAddonPreferences


class SetLogLevel(bpy.types.Operator):
    """Enable/disable more verbose logging to console"""

    bl_idname = "rhubarb.set_log_level"
    bl_label = "Log level"
    bl_description = __doc__
    bl_options = {'UNDO', 'REGISTER'}

    level: EnumProperty(  # type: ignore
        name="Log Level",
        items=[
            (str(logging.FATAL), 'FATAL', ""),
            (str(logging.ERROR), 'ERROR', ""),
            (str(logging.WARNING), 'WARNING', ""),
            (str(logging.INFO), 'INFO', ""),
            (str(logging.DEBUG), 'DEBUG', ""),
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
