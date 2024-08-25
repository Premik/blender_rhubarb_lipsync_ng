import logging
import os
import pathlib
from typing import Any

import bpy
from bpy.types import Context, Sound

from ..rhubarb.rhubarb_command import RhubarbCommandAsyncJob
from . import ui_utils
from .capture_properties import CaptureListProperties, CaptureProperties, JobProperties, MouthCueList
from .preferences import RhubarbAddonPreferences

log = logging.getLogger(__name__)


def rhubarcli_validation(context: Context) -> str:
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

    # last_op: 'ProcessSoundFile' = None  # To support unit tests. No good way to find running ops in Blender API
    last_op = None  # To support unit tests. No good way to find running ops in Blender API

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        props = CaptureListProperties.capture_from_context(context)
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

    def invoke(self, context: Context, event: bpy.types.Event) -> set[Any]:
        props = CaptureListProperties.capture_from_context(context)
        cl: MouthCueList = props.cue_list
        if len(cl.items) > 0:
            # Already some existing cues, confirm before overriding
            wm = context.window_manager
            return wm.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context: Context) -> set[str]:
        ProcessSoundFile.last_op = self  # type: ignore
        prefs = RhubarbAddonPreferences.from_context(context)
        rootProps = CaptureListProperties.from_context(context)
        props = CaptureListProperties.capture_from_context(context)
        jprops: JobProperties = props.job
        lst: MouthCueList = props.cue_list
        lst.items.clear()

        sound: Sound = props.sound
        jprops.cancel_request = False  # Clear any (stalled)  cancel request states
        self.cancel_on_next = False
        cmd = prefs.new_command_handler()

        self.job = RhubarbCommandAsyncJob(cmd)
        snd_path = ui_utils.to_abs_path(sound.filepath)
        dialog_file_path = props.dialog_file
        if not dialog_file_path:  # Dialog file not specified, try txt file based on the sound file
            dialog_file_path = os.path.splitext(snd_path)[0] + '.txt'
            if os.path.exists(dialog_file_path):
                log.info(f"Found dialog file {dialog_file_path}")
            else:
                dialog_file_path = None

        cmd.lipsync_start(snd_path, dialog_file_path)
        self.report({'INFO'}, "Started")

        wm = context.window_manager
        wm.modal_handler_add(self)
        self.timer = wm.event_timer_add(0.2, window=context.window)
        # self.object_name = context.object.name  # Save the current active object name in case the selection chagned later
        # Save index of the currently selected capture in case the selection chagned while the job is still running
        self.capture_index = rootProps.index
        self.update_progress(context)
        log.debug("Operator execute")
        return {'RUNNING_MODAL'}

    def running_props(self, context: Context) -> CaptureProperties:
        """Properties bound to capture when the operator has been started.
        Since the operator is modal (background) the selected capture can be changed while operator is still running
        """
        # TODO: Ensure the self.object has not beed delete in the meantime(save id(obj) or obj.as_pointer() ?)
        # return CaptureProperties.by_object_name(self.object_name)
        rootProps = CaptureListProperties.from_context(context)
        if self.capture_index < 0 or self.capture_index >= len(rootProps.items):
            return None
        return rootProps.items[self.capture_index]

    # @property
    # def running_job(self) -> Optional[RhubarbCommandAsyncJob]:
    #    return ProcessSoundFile.get_job_from_obj(self.object)

    def modal(self, context: Context, event: bpy.types.Event) -> set[str]:
        # print(f"{id(self)}  {id(context.object)}")

        if not self.job:
            self.report({'ERROR'}, "No job object found registered for the active object")
            self.finished(context)
            return {'CANCELLED'}

        if not self.running_props(context):
            msg = f"Failed get the capture at index: '{self.capture_index}'.\n Object delete or renamed?"
            self.report({'ERROR'}, msg)
            self.job.last_exception = Exception(msg)
            self.job.cancel()
            self.finished(context)
            return {'CANCELLED'}

        jprops: JobProperties = self.running_props(context).job
        if event and event.type in {'ESC'} or jprops.cancel_request:
            jprops.cancel_request = False
            self.cancel_on_next = True
            log.info("Received cancel request. Will cancel on next update")
            self.report({'INFO'}, "Cancel")
            jprops.status = "Cancelling"
            # https://blender.stackexchange.com/questions/157227/how-to-redraw-status-bar-in-blender-2-80
            context.workspace.status_text_set_internal(None)
            # Defere the actuall canceling to give Blender UI chance to update (show the Cancel report)
            return {'PASS_THROUGH'}

        try:
            progress = self.job.lipsync_check_progress_async()
            if self.job.cmd.has_finished:
                self.report({'INFO'}, f"Capture @{self.capture_index} Done")
                self.finished(context)
                return {'FINISHED'}

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
        # Only changes mouse cursor, looks ugly
        # if progress == 0:
        #    # https://blender.stackexchange.com/questions/1050/blender-ui-multithreading-progressbar
        #    wm.progress_begin(0, 100)
        # else:
        #    wm.progress_update(progress)
        # Slider can only display value from  a blender property. And properties can't be modified in the draw methods, so setting here
        if self.running_props(context):
            jprops: JobProperties = self.running_props(context).job
            jprops.update_from_async_job(self.job)
        ui_utils.redraw_3dviews(context)

    def finished(self, context: Context) -> None:
        log.info("Operator finished")

        wm = context.window_manager
        wm.event_timer_remove(self.timer)

        del self.timer
        ProcessSoundFile.last_op = None
        if self.job:
            self.job.last_progress = 100
            self.update_progress(context)
            self.job.join_threads()
            self.job.cmd.close_process()
            props = self.running_props(context)
            if props:
                lst: MouthCueList = props.cue_list
                cues = self.job.get_lipsync_output_cues()
                lst.add_cues(cues)
                log.info(f"Added {len(cues)} cues to the list")
                # Ensure  the mapping list is initialized. As it would be likely needed anyway
                # mp: MappingProperties = props.mapping
                # mp.build_items()

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
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, rhubarcli_validation)

    def execute(self, context: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(context)
        cmd = prefs.new_command_handler()
        GetRhubarbExecutableVersion.executable_version = cmd.get_version()
        # Cache to alow re-run on config changes
        GetRhubarbExecutableVersion.executable_last_path = str(cmd.executable_path)
        return {'FINISHED'}
