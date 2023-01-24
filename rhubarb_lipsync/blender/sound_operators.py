from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context, Sound, SoundSequence

from typing import Optional, List, Dict, cast
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, IntProperty, EnumProperty
from rhubarb_lipsync.blender.properties import CaptureProperties, RhubarbAddonPreferences
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
    bl_description = __doc__

    codec: EnumProperty(  # type: ignore
        name="Codec",
        items=[
            ("ogg", "ogg", "Ogg (Vorbis)"),
            ("wav", "wav", "Wav (PCM)"),
        ],
        default="ogg",
    )

    channels_configs = {
        'INVALID': (str(aud.CHANNELS_INVALID), 'INVALID', ""),
        'MONO': (str(aud.CHANNELS_MONO), 'MONO', ""),
        'STEREO': (str(aud.CHANNELS_STEREO), 'STEREO', ""),
        'STEREO_LFE': (str(aud.CHANNELS_STEREO_LFE), 'STEREO_LFE', ""),
        'CHANNELS_4': (str(aud.CHANNELS_SURROUND4), 'CHANNELS_4', ""),
        'CHANNELS_5': (str(aud.CHANNELS_SURROUND5), 'CHANNELS_5', ""),
        'SURROUND_51': (str(aud.CHANNELS_SURROUND51), 'SURROUND_51', ""),
        'SURROUND_61': (str(aud.CHANNELS_SURROUND61), 'SURROUND_61', ""),
        'SURROUND_71': (str(aud.CHANNELS_SURROUND71), 'SURROUND_71', ""),
    }

    rate: IntProperty(name="Rate", description="Sample-rate of the audio in Hz", min=4000, max=64000)  # type: ignore
    channels: EnumProperty(name="Channels", items=channels_configs.values(), default=str(aud.CHANNELS_MONO))  # type: ignore
    format: EnumProperty(  # type: ignore
        name="Format",
        items=[
            (str(aud.FORMAT_INVALID), 'INVALID', ""),
            (str(aud.FORMAT_U8), 'FORMAT_U8', ""),
            (str(aud.FORMAT_S16), 'FORMAT_S16', ""),
            (str(aud.FORMAT_S24), 'FORMAT_S24', ""),
            (str(aud.FORMAT_S32), 'FORMAT_S32', ""),
            (str(aud.FORMAT_FLOAT32), 'FORMAT_FLOAT32', ""),
            (str(aud.FORMAT_FLOAT64), 'FORMAT_FLOAT64', ""),
        ],
        default=str(aud.FORMAT_U8),
    )
    bitrate: IntProperty(name="Bitrate", description="", default=128 * 1024, min=16 * 1024, max=256 * 1024)  # type: ignore

    write_configs = {
        "ogg": (aud.CONTAINER_OGG, aud.CODEC_VORBIS),
        "wav": (aud.CONTAINER_WAV, aud.CODEC_PCM),
    }

    @property
    def write_config(self) -> tuple[int, int, int]:
        return ConvertSoundFromat.write_configs.get(self.codec, None)  # type: ignore

    target_folder: StringProperty(name="Target folder", subtype='FILE_PATH')  # type: ignore
    target_filename: StringProperty(name="Target name")  # type: ignore

    @property
    def target_path_full(self) -> pathlib.Path:
        folder = pathlib.Path(bpy.path.abspath(self.target_folder))
        return folder / pathlib.Path(self.target_filename)

    @staticmethod
    def init_props_from_sound(op_props, context: Context) -> None:

        prefs = RhubarbAddonPreferences.from_context(context)
        props = CaptureProperties.from_context(bpy.context)
        """Init the self's props from layout.prop call."""
        this = cast(ConvertSoundFromat, op_props)  #  The op_props arg contains the same set of properties as self)
        sound: Sound = props.sound
        this.rate = sound.samplerate
        # Map sound's channel enum (string) to aud constant (int).
        ch_cfg = ConvertSoundFromat.channels_configs
        ch = ch_cfg.get(sound.channels, ch_cfg['INVALID'])
        this.channels = ch[0]  # Enum id = aud constant

        # this.channels = sound.channels

        if prefs.default_converted_output_folder:
            this.target_folder = prefs.default_converted_output_folder
        else:
            this.target_folder = props.sound_file_folder
        this.target_filename = props.get_sound_name_with_new_extension(this.codec)

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

    def draw(self, context: Context):

        layout = self.layout
        layout.prop(self, "codec")
        ui_utils.draw_prop_with_label(self, "rate", "Rate", layout)
        layout.prop(self, "channels")
        layout.prop(self, "format")
        ui_utils.draw_prop_with_label(self, "bitrate", "Bitrate", layout)
        layout.separator()

        layout.prop(self, "target_folder")
        layout.prop(self, "target_filename")
        if self.target_path_full and self.target_path_full.exists():
            ui_utils.draw_error(self.layout, f"The file exists and will be overwritten:\n{self.target_path_full}")
            # ui_utils.draw_error(self.layout, f"exists and will be overwritten.")

    def invoke(self, context: Context, event) -> set[int] | set[str]:
        # Open dialog
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: Context) -> set[str]:

        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound
        src_path = pathlib.Path(bpy.path.abspath(sound.filepath))
        bpy.context.window.cursor_set("WAIT")
        asound = aud.Sound(str(src_path))
        args = {
            "filename": str(self.target_path_full),
            "rate": self.rate,
            "channels": int(self.channels),
            "format": int(self.format),
            "container": self.write_config[0],
            "codec": self.write_config[1],
            "bitrate": self.bitrate,
            "buffersize": 64 * 1024,
        }
        log.info(f"Saving {self.target_path_full}. \n{args}")
        try:
            bpy.context.window.cursor_set("WAIT")
            asound.write(**args)
        finally:
            bpy.context.window.cursor_set("DEFAULT")

        return {'FINISHED'}
