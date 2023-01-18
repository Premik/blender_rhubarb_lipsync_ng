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


# bpy.ops.sequencer.sound_strip_add(
# filepath="/tmp/work/1.flac", directory="/tmp/work/",
# files=[{"name":"1.flac", "name":"1.flac"}],
# frame_start=23, channel=1,
# overlap_shuffle_override=True)

# C.active_sequence_strip
# bpy.data.scenes['Scene'].sequence_editor.sequences_all["en_male_electricity.ogg"]


def sound_strips_common_validation(context: Context) -> str:
    selection_error = ui_utils.context_selection_validation(context)
    if selection_error:
        return selection_error
    props = CaptureProperties.from_context(context)
    if not props.sound:
        return "No sound selected"
    return ""


class RemoveSoundStripWithSound(bpy.types.Operator):
    """Remove the sound strip which has the current sound the source."""

    bl_idname = "rhubarb.remove_sound_strip"
    bl_label = "Remove strip"
    bl_description = __doc__
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        error_common = sound_strips_common_validation(context)
        if error_common:
            return error_common
        props = CaptureProperties.from_context(context)
        strip = props.find_strips_of_sound(context)
        if not strip:
            return f"No strip using the current sound found."
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
        strips = props.find_strips_of_sound(context)
        assert strips
        seq_editor = context.scene.sequence_editor
        # Seems ctx override doesn't work like that. At least not for sequence editor
        # selection = {'active_sequence_strip': strips[0], 'selected_sequences': strips}
        old_selection = seq_editor.active_strip
        try:
            seq_editor.active_strip = strips[0]
            sctx = ui_utils.get_sequencer_context(context)
            with context.temp_override(**sctx):  # type: ignore
                ui_utils.assert_op_ret(bpy.ops.sequencer.delete())
        finally:
            # seq_editor.active_strip = old_selection
            pass
        return {'FINISHED'}


# https://stackoverflow.com/questions/53215355/whit-python-in-blender-insert-an-effect-strip-as-wipe-in-the-video-sequence-edi
# se=C.scene.sequence_editor
# se.sequences.new_sound("myseq", "/tmp/work/1.flac", 2,1)


class CreateSoundStripWithSound(bpy.types.Operator):
    """Create new soun strip and send this sound as the source. So that it can be heard during playback"""

    bl_idname = "rhubarb.place_sound_strip"
    bl_label = "Place as strip"
    bl_description = __doc__
    bl_options = {'UNDO', 'REGISTER'}

    start_frame: IntProperty(name="Start Frame", default=1)
    channel: IntProperty(name="Channel", default=1)
    show_waveform: BoolProperty(name="Show Waveform", default=True)

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        error_common = sound_strips_common_validation(context)
        if error_common:
            return error_common
        props = CaptureProperties.from_context(context)
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

    def draw(self, context: Context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "start_frame")

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
