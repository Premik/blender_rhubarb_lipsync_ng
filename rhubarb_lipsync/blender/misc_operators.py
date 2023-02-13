import logging
from functools import cached_property
from types import ModuleType
from typing import Dict, List, Optional, cast

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty, BoolProperty
from bpy.types import Context

import rhubarb_lipsync.blender.auto_load
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.rhubarb.log_manager import logManager
import rhubarb_lipsync.blender.ui_utils as ui_utils
import traceback

log = logging.getLogger(__name__)


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


class PlayAndStop(bpy.types.Operator):
    """Starts animation playback from the current frame and stops automatically after played certain number of frames."""

    bl_idname = "rhubarb.play_and_stop"
    bl_label = "Play and Stop"

    play_frames: IntProperty(name="Frames", description="Number of frames to play", default=100)  # type: ignore
    restore_frame: BoolProperty(name="Restore frame", description="Jump back to the start frame after playback is done")  # type: ignore
    frames_left = 0

    @staticmethod
    def on_frame(scene):
        if log.isEnabledFor(logging.DEBUG):
            log.debug(f"On frame {PlayAndStop.frames_left}")
        PlayAndStop.frames_left -= 1
        if PlayAndStop.frames_left <= 0:
            log.debug("Stopping playback. Counter reached zero.")
            try:
                bpy.ops.screen.animation_cancel(restore_frame=False)
                # print(list(bpy.app.handlers.frame_change_post))
                fn = PlayAndStop.on_frame
                handlers = bpy.app.handlers.frame_change_post
                if not ui_utils.remove_handler(handlers, fn):
                    log.warn(f"Coulnd't remove handler {ui_utils.func_fqname(fn)}. Not found:\n{handlers}")
            except:
                log.error(f"Unexpected error while stopping the animation")
                traceback.print_exception()

    @classmethod
    def disabled_reason(cls, context: Context, limit=0) -> str:
        if getattr(context.screen, 'is_animation_playing', False):
            return f"Animation is playing. Counter:{PlayAndStop.frames_left}"
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        # return ui_utils.validation_poll(cls, context)
        return True

    def execute(self, context: Context) -> set[str]:

        # wm = context.window_manager
        # wm.modal_handler_add(self)
        # self.timer = wm.event_timer_add(0.1, window=context.window)
        # return {'RUNNING_MODAL'}
        PlayAndStop.frames_left = self.play_frames
        log.debug(f"Starting animation playback. With counter {self.play_frames}.")
        if not getattr(context.screen, 'is_animation_playing', False):
            bpy.ops.screen.animation_play()  # Another play call would stop the playback if already playing
        bpy.app.handlers.frame_change_post.append(PlayAndStop.on_frame)
        return {'FINISHED'}

    def modal(self, context: Context, event) -> set[str]:

        # if event.type in {'ESC'}:
        # return {'CANCELLED'}

        try:
            # progress = job.lipsync_check_progress_async()
            pass
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'PASS_THROUGH'}
