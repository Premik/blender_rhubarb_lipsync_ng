from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context, Sound, SoundSequence

from typing import Optional, List, Dict, cast
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, IntProperty, EnumProperty
from rhubarb_lipsync.blender.properties import CaptureProperties
import rhubarb_lipsync.blender.ui_utils as ui_utils
import pathlib
import aud


log = logging.getLogger(__name__)

# Limit the strip-search on the poll methods. When limit is reach the op would be enabled but fail on execution instead
poll_search_limit = 50

# bpy.ops.sequencer.sound_strip_add(
# filepath="/tmp/work/1.flac", directory="/tmp/work/",
# files=[{"name":"1.flac", "name":"1.flac"}],
# frame_start=23, channel=1,
# overlap_shuffle_override=True)

# C.active_sequence_strip
# bpy.data.scenes['Scene'].sequence_editor.sequences_all["en_male_electricity.ogg"]


def sound_common_validation(context: Context) -> str:
    selection_error = ui_utils.context_selection_validation(context)
    if selection_error:
        return selection_error
    props = CaptureProperties.from_context(context)
    if not props.sound:
        return "No sound selected"
    return ""


class CreateSoundStripWithSound(bpy.types.Operator):
    """Create new sound strip and set the selected sound as the source. So the selected sound can be heard during playback"""

    bl_idname = "rhubarb.place_sound_strip"
    bl_label = "Place as strip"
    bl_description = __doc__
    bl_options = {'UNDO', 'REGISTER'}

    start_frame: IntProperty(name="Start Frame", default=1)  # type: ignore
    channel: IntProperty(name="Channel", default=1)  # type: ignore
    show_waveform: BoolProperty(name="Show Waveform", default=True)  # type: ignore

    @classmethod
    def disabled_reason(cls, context: Context, limit=0) -> str:
        error_common = sound_common_validation(context)
        if error_common:
            return error_common
        props = CaptureProperties.from_context(context)
        strip = props.find_strips_of_sound(context, limit)
        if strip:
            return f"Already placed on a strip on the channel {strip[0].channel} at frame {strip[0].frame_start}."
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        m = cls.disabled_reason(context, poll_search_limit)  # Search limit, for perf. reasons
        if not m:
            return True
        # Following is not a class method per doc. But seems to work like it
        cls.poll_message_set(m)  # type: ignore
        return False

    def execute(self, context: Context) -> set[str]:

        error = self.disabled_reason(context)  # Run validation again, without the limit this time
        if error:
            self.report({"ERROR"}, error)
            return {'CANCELLED'}
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound

        # sctx = ui_utils.get_sequencer_context(context)
        # with context.temp_override(**sctx):
        #     ui_utils.assert_op_ret(
        #         bpy.ops.sequencer.sound_strip_add(
        #             filepath=props.sound.filepath,
        #             frame_start=self.start_frame,
        #             channel=self.channel,
        #         )
        #     )

        # https://stackoverflow.com/questions/53215355/whit-python-in-blender-insert-an-effect-strip-as-wipe-in-the-video-sequence-edi
        se = context.scene.sequence_editor
        se.sequences.new_sound(sound.name_full, sound.filepath, self.start_frame, self.channel)

        # The above op always create a new sound, even when there is the same one already imported.
        # Find the newly created strip and change its sound back to the selected one
        strips = props.find_strips_of_sound(context)
        assert strips, f"Was not able to locate the newly placed sound strip with the '{sound.filepath}'."
        if len(strips) > 1:
            self.report({"ERROR"}, f"There is more than one sound strips using the sound with '{sound.filepath}'.")
            return {'CANCELLED'}

        strip = strips[0]
        oldSound = strip.sound
        assert oldSound
        # Set to the current sound instead. This would leave the newly created copy with 0 users.
        strip.sound = sound
        strip.show_waveform = self.show_waveform
        # Remove the newly created sound sound
        # https://blender.stackexchange.com/questions/27234/python-how-to-completely-remove-an-object
        bpy.data.sounds.remove(oldSound, do_unlink=True)
        return {'FINISHED'}


class RemoveSoundStripWithSound(bpy.types.Operator):
    """Remove the sound strip which has the current sound the source."""

    bl_idname = "rhubarb.remove_sound_strip"
    bl_label = "Remove strip"
    bl_description = __doc__
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def disabled_reason(cls, context: Context, limit=0) -> str:
        error_common = sound_common_validation(context)
        if error_common:
            return error_common
        props = CaptureProperties.from_context(context)
        strip = props.find_strips_of_sound(context, limit)
        if not strip:
            return f"No strip using the current sound found."
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        m = cls.disabled_reason(context, poll_search_limit)
        if not m:
            return True
        # Following is not a class method per doc. But seems to work like it
        cls.poll_message_set(m)  # type: ignore
        return False

    def execute(self, context: Context) -> set[str]:
        error = self.disabled_reason(context)  # Run validation again, without the limit this time
        if error:
            self.report({"ERROR"}, error)
            return {'CANCELLED'}
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound
        strips = props.find_strips_of_sound(context)
        assert strips
        if len(strips) > 1:
            m = f"There is more than one sound strips using the sound with '{sound.filepath}'. Don't know which one to remove."
            self.report({"ERROR"}, m)
            return {'CANCELLED'}
        se = context.scene.sequence_editor
        se.sequences.remove(strips[0])
        return {'FINISHED'}


class ConvertSoundFromat(bpy.types.Operator):
    """Convert the sound to a different format"""

    bl_idname = "rhubarb.sound_convert"
    bl_label = "Convert"

    codec: EnumProperty(  # type: ignore
        name="Codec",
        items=[
            ("ogg", "ogg", "Ogg (Vorbis)"),
            ("wav", "wav", "Wav (PCM)"),
        ],
        default="ogg",
    )

    rate: IntProperty(name="Rate", description="Samplerate of the audio in Hz")  # type: ignore

    write_configs = {
        "ogg": (aud.CODEC_VORBIS, aud.CONTAINER_OGG),
        "wav": (aud.CODEC_PCM, aud.CONTAINER_WAV),
    }

    # filename (string) – The path to write to.
    # rate (int) – The sample rate to write with.
    # channels (int) – The number of channels to write with.
    # format (int) – The sample format to write with.
    # container (int) – The container format for the file.
    # codec (int) – The codec to use in the file.
    # bitrate (int) – The bitrate to write with.
    # buffersize (int) – The size of the writing buffer.

    @staticmethod
    def init_props_from_sound(props, sound: Sound) -> None:
        """Init the self's props from layout.prop call."""
        this = cast(ConvertSoundFromat, props)  #  The props arg contains the same set of properties as self)
        this.rate = sound.samplerate

    @classmethod
    def description(csl, context: Context, self: 'ConvertSoundFromat') -> str:
        return f"Convert the selected sound to {self.codec}"

    @classmethod
    def disabled_reason(cls, context: Context, limit=0) -> str:
        error_common = sound_common_validation(context)
        if error_common:
            return error_common
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound
        if sound.packed_file:
            return "Please unpack the sound first."
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        m = cls.disabled_reason(context)
        if not m:
            return True
        # Following is not a class method per doc. But seems to work like it
        cls.poll_message_set(m)  # type: ignore
        return False

    def invoke(self, context: Context, event) -> set[int] | set[str]:
        # Open dialog
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: Context) -> set[str]:
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound
        asound = aud.Sound(sound.filepath)
        # asound.write

        return {'FINISHED'}
