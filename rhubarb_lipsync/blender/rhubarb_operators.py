import logging
import pathlib
from io import TextIOWrapper
from typing import Dict, List, Optional, cast

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, Sound, SoundSequence

import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.blender.properties import CaptureProperties, MouthCueList, JobProperties
from rhubarb_lipsync.rhubarb.log_manager import logManager
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob, RhubarbCommandWrapper
from collections import defaultdict

log = logging.getLogger(__name__)


def rhubarcli_validation(context: Context, required_unpack=True) -> str:
    prefs = RhubarbAddonPreferences.from_context(context)
    cmd = prefs.new_command_handler()
    cmd_error = cmd.config_errors()
    if cmd_error:
        return cmd_error
    return ""


class ProcessSoundFile(bpy.types.Operator):
    """Process the selected sound file using the rhubarb executable"""

    bl_idname = "rhubarb.process_sound_file"
    bl_label = "Capture"

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound
        # Use properties (binded to object) to check if already running.
        # This allows concurent running of the op provided each instance is linked to a different object
        jprops: JobProperties = props.job

        if jprops.running:
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
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def invoke(self, context: Context, event) -> set[int] | set[str]:
        props = CaptureProperties.from_context(context)
        cl: MouthCueList = props.cue_list
        if len(cl.items) > 0:
            # Already some existing cues, confirm before overriding
            wm = context.window_manager
            return wm.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(context)
        props = CaptureProperties.from_context(context)
        jprops: JobProperties = props.job

        sound: Sound = props.sound
        jprops.cancel_request = False  # Clear any (stalled)  cancel request states
        self.cancel_on_next = False
        cmd = prefs.new_command_handler()

        self.job = RhubarbCommandAsyncJob(cmd)
        cmd.lipsync_start(ui_utils.to_abs_path(sound.filepath), props.dialog_file)
        self.report({'INFO'}, f"Started")

        wm = context.window_manager
        wm.modal_handler_add(self)
        self.timer = wm.event_timer_add(0.2, window=context.window)
        self.object_name = context.object.name  # Save the current active object name in case the selection chagned later
        self.update_progress(context)
        log.debug("Operator execute")
        return {'RUNNING_MODAL'}

    @property
    def running_props(self) -> CaptureProperties:
        """Properties bound to the object when the operator has been started.
        Since the operator is modal (background) the selected object can be changed while operator is still running
        """
        # TODO: Ensure the self.object has not beed delete in the meantime(save id(obj) or obj.as_pointer() ?)
        return CaptureProperties.by_object_name(self.object_name)

    @property
    def running_job(self) -> Optional[RhubarbCommandAsyncJob]:
        return ProcessSoundFile.get_job_from_obj(self.object)

    def modal(self, context: Context, event: bpy.types.Event) -> set[str]:
        # print(f"{id(self)}  {id(context.object)}")

        if not self.job:
            self.report({'ERROR'}, f"No job object found registered for the active object")
            self.finished(context)
            return {'CANCELLED'}

        if not self.running_props:
            msg = f"Failed get the properties \nfrom the '{self.object_name}' object.\n Object delete or renamed?"
            self.report({'ERROR'}, msg)
            self.job.last_exception = Exception(msg)
            self.job.cancel()
            self.finished(context)
            return {'CANCELLED'}

        if self.job.cmd.has_finished:
            self.report({'INFO'}, f"{self.object_name} Done")

            self.finished(context)
            return {'FINISHED'}

        jprops: JobProperties = self.running_props.job
        if event.type in {'ESC'} or jprops.cancel_request:
            jprops.cancel_request = False
            self.cancel_on_next = True
            log.info("Received cancel request. Will cancel on next update")
            self.report({'INFO'}, f"Cancel")
            jprops.status = "Cancelling"
            # https://blender.stackexchange.com/questions/157227/how-to-redraw-status-bar-in-blender-2-80
            context.workspace.status_text_set_internal(None)
            # Defere the actuall canceling to give Blender UI chance to update (show the Cancel report)
            return {'PASS_THROUGH'}

        try:
            progress = self.job.lipsync_check_progress_async()
        except Exception as e:
            self.report({'ERROR'}, str(e))
            log.exception(e)
            self.job.cancel()
            if not self.job.last_exception:
                self.job.last_exception = e
            self.finished(context)
            return {'CANCELLED'}

        if progress is not None:
            self.update_progress(context)
            # self.report({'INFO'}, f"{progress}%")

        if self.cancel_on_next:
            log.info("Cancelling the operator")
            self.job.cancel()
            self.finished(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def update_progress(self, context: Context) -> None:
        wm = context.window_manager

        # Only changes mouse cursor, looks ugly
        # if progress == 0:
        #    # https://blender.stackexchange.com/questions/1050/blender-ui-multithreading-progressbar
        #    wm.progress_begin(0, 100)
        # else:
        #    wm.progress_update(progress)
        # Slider can only display value from  a blender property. And properties can't be modified in the draw methods, so setting here
        if self.running_props:
            jprops: JobProperties = self.running_props.job
            jprops.update_from_async_job(self.job)
        context.area.tag_redraw()  # Force redraw

    def finished(self, context: Context) -> None:
        log.info("Operator finished")

        wm = context.window_manager
        wm.event_timer_remove(self.timer)
        del self.timer
        if self.job:
            self.job.last_progress = 100
            self.update_progress(context)
            self.job.join_thread()
            self.job.cmd.close_process()
            props = self.running_props
            if props:
                lst: MouthCueList = props.cue_list
                lst.add_cues(self.job.get_lipsync_output_cues())
            del self.job


class GetRhubarbExecutableVersion(bpy.types.Operator):
    """Run the rhubarb executable and collect the version info."""

    bl_idname = "rhubarb.get_executable_version"
    bl_label = "Check rhubarb version"

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
    def poll(cls, context) -> bool:
        return ui_utils.validation_poll(cls, context, rhubarcli_validation)

    def execute(self, context: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(context)
        cmd = prefs.new_command_handler()
        GetRhubarbExecutableVersion.executable_version = cmd.get_version()
        # Cache to alow re-run on config changes
        GetRhubarbExecutableVersion.executable_last_path = str(cmd.executable_path)
        return {'FINISHED'}


class CancelCaptureJob(bpy.types.Operator):
    """Cancels the running caputre job"""

    bl_idname = "rhubarb.cancel_job"
    bl_label = "Cancel"

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        selection_error = CaptureProperties.context_selection_validation(context)
        if selection_error:
            return selection_error
        props = CaptureProperties.from_context(context)

        return ""

    @classmethod
    def poll(cls, context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def execute(self, context: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(context)
        cmd = prefs.new_command_handler()
        GetRhubarbExecutableVersion.executable_version = cmd.get_version()
        # Cache to alow re-run on config changes
        GetRhubarbExecutableVersion.executable_last_path = str(cmd.executable_path)
        return {'FINISHED'}


class ClearCueList(bpy.types.Operator):
    """Removes all captured cues from the cue list"""

    bl_idname = "rhubarb.clear_cue_list"
    bl_label = "Clear the cue list"
    bl_options = {'UNDO'}

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        selection_error = CaptureProperties.context_selection_validation(context)
        if selection_error:
            return selection_error
        props = CaptureProperties.from_context(context)
        cl: MouthCueList = props.cue_list
        if len(cl.items) <= 0:
            return "Cue list is empty"
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    # def invoke(self, context: Context, event) -> set[int] | set[str]:
    #    wm = context.window_manager
    #    return wm.invoke_confirm(self, event)

    def execute(self, context: Context) -> set[str]:
        props = CaptureProperties.from_context(context)
        cl: MouthCueList = props.cue_list
        cl.items.clear()

        return {'FINISHED'}
