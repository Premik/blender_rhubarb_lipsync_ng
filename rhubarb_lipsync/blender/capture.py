from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context, Sound, SoundSequence

from typing import Optional, List, Dict, cast
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, IntProperty
from rhubarb_lipsync.blender.properties import CaptureProperties
import rhubarb_lipsync.blender.ui_utils as ui_utils
import pathlib

log = logging.getLogger(__name__)


def context_selection_validation(ctx: Context) -> str:
    if not ctx.object:
        return "No active object selected"
    if not CaptureProperties.from_context(ctx):
        return "'rhubarb_lipsync' not found on the active object"
    return ""


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
            layout.operator(PlaceSoundOnStrip.bl_idname)
            layout.operator('sequencer.sound_strip_add')
            selection_error = context_selection_validation(context)
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

            layout.operator(ProcessSoundFile.bl_idname)

        except Exception as e:
            self.draw_error("Unexpected error.")
            self.draw_error(str(e))
            raise
        finally:
            self.ctx = None  # type: ignore


# bpy.ops.sequencer.sound_strip_add(
# filepath="/tmp/work/1.flac", directory="/tmp/work/",
# files=[{"name":"1.flac", "name":"1.flac"}],
# frame_start=23, channel=1,
# overlap_shuffle_override=True)

# C.active_sequence_strip
# bpy.data.scenes['Scene'].sequence_editor.sequences_all["en_male_electricity.ogg"]


class PlaceSoundOnStrip(bpy.types.Operator):
    """Place the sound on a sound strip. So that it can be heard during playback"""

    bl_idname = "rhubarb.place_sound_on_strip"
    bl_label = "Place on strip"
    bl_description = __doc__
    bl_options = {'UNDO', 'REGISTER'}

    start_frame: IntProperty(name="Start Frame", default=1)
    channel: IntProperty(name="Channel", default=1)
    show_waveform: BoolProperty(name="Show Waveform", default=True)

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        selection_error = context_selection_validation(context)
        if selection_error:
            return selection_error
        props = CaptureProperties.from_context(context)
        if not props.sound:
            return "No sound selected"
        strip = props.find_strips_of_sound(context)
        if strip:
            return f"Already placed on a strip on the channel {strip[0].channel} at frame {strip[0].frame_start}."
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        m = cls.disabled_reason(context)
        if not m:
            return True
        # Following is not a class method per doc. But seems to work like it
        cls.poll_message_set(m)  # type: ignore
        return False

    def execute(self, context: Context) -> set[str]:
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound

        sctx = ui_utils.get_sequencer_context(context)
        with context.temp_override(**sctx):
            ui_utils.assert_op_ret(
                bpy.ops.sequencer.sound_strip_add(
                    filepath=props.sound.filepath,
                    frame_start=self.start_frame,
                    channel=self.channel,
                )
            )
        # The above op always create a new sound, even when there is the same one already imported.
        # Find the newly created strip and change its sound back to the selected one
        strips = props.find_strips_of_sound(context)
        assert strips, f"Was not able to locate the newly placed sound strip {sctx}"
        assert len(strips) == 1, f"There is more than one sound strips using this sound"
        strip = strips[0]
        assert strip.sound
        # Set to the current sound instead. This would leave the
        # create copy with 0 users. Letting it garbage-collected by blender on reload
        strip.sound = sound
        strip.show_waveform = self.show_waveform
        return {'FINISHED'}


class ProcessSoundFile(bpy.types.Operator):
    bl_idname = "rhubarb.process_sound_file"
    bl_label = "Capture mouth cues"
    bl_description = "Process the selected sound file using the rhubarb executable"

    @classmethod
    def poll(cls, context):
        return True
