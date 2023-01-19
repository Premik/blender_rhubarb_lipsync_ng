from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context, Sound, SoundSequence

from typing import Optional, List, Dict, cast
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, IntProperty
from rhubarb_lipsync.blender.properties import CaptureProperties, RhubarbAddonPreferences
import rhubarb_lipsync.blender.ui_utils as ui_utils
import rhubarb_lipsync.blender.sound_operators as sound_operators
import rhubarb_lipsync.blender.rhubarb_operators as rhubarb_operators
import pathlib

log = logging.getLogger(__name__)


class CaptureMouthCuesPanel(bpy.types.Panel):

    bl_idname = "RLPS_PT_capture_panel"
    bl_label = "RLPS: Mouth cues capture"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RLSP"
    # bl_parent_id= 'VIEW3D_PT_example_panel'
    # bl_description = "Tool tip"
    # bl_context = "object"

    def draw_error(self, msg: str):
        box = self.layout.box()
        box.label(text=msg, icon="ERROR")

    def draw_sound_setup(self, sound: Sound) -> bool:
        layout = self.layout
        layout.prop(sound, "filepath", text="")  # type: ignore
        if sound.packed_file:
            self.draw_error("Rhubarb requires the file on disk.")
            self.draw_error("Please unpack the sound.")
            unpackop = layout.operator("sound.unpack", icon='PACKAGE', text=f"Unpack '{sound.name}'")
            unpackop.id = sound.name_full  # type: ignore
            unpackop.method = 'USE_ORIGINAL'  # type: ignore
            return False
        path = pathlib.Path(sound.filepath)
        if not path.exists:
            self.draw_error("Sound file doesn't exist.")
            return False

        props = CaptureProperties.from_context(self.ctx)
        if not props.is_sound_format_supported():
            self.draw_error("Only wav or ogg supported.")
            return False

        return True

    def draw_info(self, sound: Sound):
        props = CaptureProperties.from_context(self.ctx)
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        if not ui_utils.draw_expandable_header(prefs, "info_panel_expanded", "Additional info", self.layout):
            return
        box = self.layout.box()
        # line = layout.split()
        line = box.split()
        line.label(text="Sample rate")
        line.label(text=f"{sound.samplerate} Hz")
        line = box.split()
        line.label(text="Channels")
        line.label(text=str(sound.channels))
        line = box.split()

        line.label(text="File extension")
        line.label(text=props.sound_file_extension)

        line = box.split()
        line.label(text="Rhubarb version")
        if RhubarbAddonPreferences.rhubarb_executable_version:
            line.label(text=RhubarbAddonPreferences.rhubarb_executable_version)
        else:
            line.operator(rhubarb_operators.GetRhubarbExecutableVersion.bl_idname)

        line = box.split()
        line.label(text="FPS")
        line.label(text=f"{self.ctx.scene.render.fps}")

    def draw(self, context: Context):
        try:
            self.ctx = context
            layout = self.layout
            layout.operator(sound_operators.CreateSoundStripWithSound.bl_idname)
            layout.operator(sound_operators.RemoveSoundStripWithSound.bl_idname)
            layout.operator('sequencer.sound_strip_add')
            selection_error = ui_utils.context_selection_validation(context)
            if selection_error:
                self.draw_error(selection_error)
                return

            # layout.prop(self.props, "sound")
            props = CaptureProperties.from_context(self.ctx)
            assert props
            layout.template_ID(props, "sound", open="sound.open")  # type: ignore
            if props.sound is None:
                self.draw_error("Select a sound file.")
                return
            if not self.draw_sound_setup(props.sound):
                self.draw_info(props.sound)
                return
            self.draw_info(props.sound)
            layout.operator(rhubarb_operators.ProcessSoundFile.bl_idname)

        except Exception as e:
            self.draw_error("Unexpected error.")
            self.draw_error(str(e))
            raise
        finally:
            self.ctx = None  # type: ignore
