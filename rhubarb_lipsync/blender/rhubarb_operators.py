from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context, Sound, SoundSequence

from typing import Optional, List, Dict, cast
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, IntProperty
from rhubarb_lipsync.blender.properties import RhubarbAddonPreferences, CaptureProperties
import rhubarb_lipsync.blender.ui_utils as ui_utils
import pathlib


def rhubarcli_validation(context: Context, required_unpack=True) -> str:
    prefs = RhubarbAddonPreferences.from_context(context)
    cmd = prefs.new_command_handler()
    cmd_error = cmd.errors()
    if cmd_error:
        return cmd_error
    return ""


class ProcessSoundFile(bpy.types.Operator):
    """Process the selected sound file using the rhubarb executable"""

    bl_idname = "rhubarb.process_sound_file"
    bl_label = "Run Rhubarb"
    bl_description = __doc__

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound
        # Use properties (binded to object) to check if already running.
        # This allows concurent running of the op provided each instance is linked to a different object
        if hasattr(props, 'running_process_sound_op'):
            if props.running_process_sound_op is not None:
                return "Already running"
        error_common = CaptureProperties.sound_selection_validation(context)
        if error_common:
            return error_common

        if not sound.filepath or not pathlib.Path(sound.filepath).exists():
            return "Sound file doesn't exist. Try absolute the path instead"

        if not props.is_sound_format_supported():
            return "Unsupported file format"
        return rhubarcli_validation(context)

    @classmethod
    def poll(cls, context):
        return ui_utils.validation_poll(cls, context)

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        props = CaptureProperties.from_context(context)

        layout = self.layout
        layout.prop(props, "dialog_file")
        layout.prop(prefs, "use_extended_shapes")

    def invoke(self, context: Context, event) -> set[int] | set[str]:
        # Open dialog
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(context)
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound
        self.cmd = prefs.new_command_handler()
        self.cmd.lipsync_start(ui_utils.to_abs_path(sound.filepath), props.dialog_file)
        self.report({'INFO'}, f"Started")

        wm = context.window_manager
        wm.modal_handler_add(self)
        self.timer = wm.event_timer_add(0.1, window=context.window)
        # https://blender.stackexchange.com/questions/1050/blender-ui-multithreading-progressbar
        wm.progress_begin(0, 100)
        props.running_process_sound_op = self
        return {'RUNNING_MODAL'}

    def modal(self, context: Context, event) -> set[str]:
        wm = context.window_manager
        try:
            if self.cmd.has_finished:
                self.report({'INFO'}, f"Done")

                self.finished(context)
                return {'FINISHED'}

            if event.type in {'ESC'}:
                self.report({'INFO'}, f"Cancel")
                self.cmd.cancel()
                self.finished(context)
                return {'CANCELLED'}

            try:
                progress = self.cmd.lipsync_check_progress_async()
            except RuntimeError as e:
                self.report({'ERROR'}, str(e))
                self.cmd.cancel()
                self.finished(context)
                return {'CANCELLED'}
        finally:
            self.finished(context)

        if progress is not None:
            wm.progress_update(progress)
            # self.report({'INFO'}, f"{progress}%")
        return {'PASS_THROUGH'}

    def finished(self, context: Context):
        props = CaptureProperties.from_context(context)
        props.running_process_sound_op = None
        wm = context.window_manager
        wm.event_timer_remove(self.timer)
        if self.cmd:
            if self.cmd.stdout:
                print(self.cmd.get_lipsync_output_cues())
            self.cmd.close_process()
            self.cmd.join_thread()
            self.cmd = None


class GetRhubarbExecutableVersion(bpy.types.Operator):
    """Run the rhubarb executable and collect the version info."""

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
    def poll(cls, context):
        return ui_utils.validation_poll(cls, context, rhubarcli_validation)

    def execute(self, context: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(context)
        cmd = prefs.new_command_handler()
        GetRhubarbExecutableVersion.executable_version = cmd.get_version()
        # Cache to alow re-run on config changes
        GetRhubarbExecutableVersion.executable_last_path = str(cmd.executable_path)
        return {'FINISHED'}
