from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context, Sound, SoundSequence

from typing import Optional, List, Dict, cast
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, IntProperty
from rhubarb_lipsync.blender.properties import RhubarbAddonPreferences, CaptureProperties
import rhubarb_lipsync.blender.ui_utils as ui_utils
import pathlib


class ProcessSoundFile(bpy.types.Operator):
    """Process the selected sound file using the rhubarb executable"""

    bl_idname = "rhubarb.process_sound_file"
    bl_label = "Run Rhubarb"
    bl_description = __doc__

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        error_common = CaptureProperties.sound_validation(context, False)
        if error_common:
            return error_common
        prefs = RhubarbAddonPreferences.from_context(context)
        cmd = prefs.new_command_handler()
        cmd_error = cmd.errors()
        if cmd_error:
            return cmd_error
        return ""

    @classmethod
    def poll(cls, context):
        return ui_utils.validation_poll(cls, context)


class GetRhubarbExecutableVersion(bpy.types.Operator):
    """Run the rhubarb executable and collect the version info. Result is stored in the addon's preferences."""

    bl_idname = "rhubarb.get_executable_version"
    bl_label = "Check rhubarb version"
    bl_description = __doc__

    executable_version = ""
    executable_last_path = ""

    @classmethod
    def get_cached_value(cls, context: Context) -> str:
        prefs = RhubarbAddonPreferences.from_context(context)
        if not cls.executable_version:
            return ""  # Has not been called yet
        if prefs.executable_path_string != GetRhubarbExecutableVersion.executable_last_path:
            return ""  # Executable path changed, requires new execution
        # Return cached version
        return cls.executable_version

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        prefs = RhubarbAddonPreferences.from_context(context)
        cmd = prefs.new_command_handler()
        cmd_error = cmd.errors()
        if cmd_error:
            return cmd_error
        return ""

    @classmethod
    def poll(cls, context):
        return ui_utils.validation_poll(cls, context)

    def execute(self, context: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(context)
        cmd = prefs.new_command_handler()
        GetRhubarbExecutableVersion.executable_version = cmd.get_version()
        # Cache to alow re-run on config changes
        GetRhubarbExecutableVersion.executable_last_path = str(cmd.executable_path)
        return {'FINISHED'}
