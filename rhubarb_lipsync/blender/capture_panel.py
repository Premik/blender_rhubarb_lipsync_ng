from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context, Sound, SoundSequence

from typing import Optional, List, Dict, cast
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, IntProperty
from rhubarb_lipsync.blender.properties import CaptureProperties
import rhubarb_lipsync.blender.ui_utils as ui_utils
import rhubarb_lipsync.blender.sound_operators as sound_operators
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

    def draw_sound_details(self, sound: Sound) -> bool:
        layout = self.layout
        layout.prop(sound, "filepath", text="")
        if sound.packed_file:
            self.draw_error("Rhubarb requires a file on disk.")
            # self.draw_error("Please unpack the sound")
            return False
        path = pathlib.Path(sound.filepath)
        if not path.exists:
            self.draw_error("Sound file doesn't exist.")
            return False
        box = layout.box()
        # line = layout.split()
        line = box.split()
        line.label(text="Sample rate")
        line.label(text=f"{sound.samplerate} Hz")
        line = box.split()
        line.label(text="Channels")
        line.label(text=str(sound.channels))
        line = box.split()

        line.label(text="File extension")
        line.label(text=path.suffix)
        if path.suffix.lower() not in [".ogg", ".wav"]:
            self.draw_error("Only wav or ogg supported.")
            return False

        return True

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
            layout.template_ID(props, "sound", open="sound.open")
            if props.sound is None:
                self.draw_error("Select a sound file.")
                return
            if not self.draw_sound_details(props.sound):
                return

            layout.operator(sound_operators.ProcessSoundFile.bl_idname)

        except Exception as e:
            self.draw_error("Unexpected error.")
            self.draw_error(str(e))
            raise
        finally:
            self.ctx = None  # type: ignore
