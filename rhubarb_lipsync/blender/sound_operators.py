import logging
import pathlib
from io import TextIOWrapper
import traceback
from typing import Dict, List, Optional, cast

import aud
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, Sound, SoundSequence

import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.blender.properties import CaptureProperties

log = logging.getLogger(__name__)

# Limit the strip-search on the poll methods. When limit is reach the op would be enabled but fail on execution instead
poll_search_limit = 50


def find_strips_of_sound(context: Context, limit=0) -> list[SoundSequence]:
    '''Finds a sound strip which is using the selected sounds.'''
    ret: list[SoundSequence] = []
    props = CaptureProperties.from_context(context)
    sound: Sound = props.sound
    if not sound:
        return []

    for i, sq in enumerate(context.scene.sequence_editor.sequences_all):
        if limit > 0 and i > limit:
            break  # Limit reached, break the search (for performance reasons)
        if not hasattr(sq, "sound"):
            continue  # Not a sound strip
        ssq = cast(SoundSequence, sq)
        foundSnd = ssq.sound
        if foundSnd is None:
            continue  # An empty strip
        if sound == foundSnd:
            ret.insert(0, ssq)  # At the top, priority
            continue
        if bpy.path.abspath(sound.filepath) == bpy.path.abspath(foundSnd.filepath):
            ret.append(ssq)  # Match by name, append to end
    return ret


def find_sounds_by_path(sound_path: str) -> list[Sound]:
    sound_path = bpy.path.abspath(sound_path)
    unpacked_sounds = [s for s in bpy.data.sounds if s.filepath and not s.packed_file]
    return [s for s in unpacked_sounds if bpy.path.abspath(s.filepath) == sound_path]


class CreateSoundStripWithSound(bpy.types.Operator):
    """Create new sound strip and set the selected sound as the source. So the selected sound can be heard during playback"""

    bl_idname = "rhubarb.place_sound_strip"
    bl_label = "Place as strip"
    bl_options = {'UNDO', 'REGISTER'}

    start_frame: IntProperty(name="Start Frame", default=1)  # type: ignore
    channel: IntProperty(name="Channel", default=1)  # type: ignore
    show_waveform: BoolProperty(name="Show Waveform", default=True)  # type: ignore

    @classmethod
    def disabled_reason(cls, context: Context, limit=poll_search_limit) -> str:
        error_common = CaptureProperties.sound_selection_validation(context, False)
        if error_common:
            return error_common
        props = CaptureProperties.from_context(context)
        strip = find_strips_of_sound(context, limit)
        if strip:
            return f"Already placed on a strip on the channel {strip[0].channel} at frame {strip[0].frame_start}."
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def invoke(self, context: Context, event) -> set[int] | set[str]:
        # Open dialog
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)

    def execute(self, context: Context) -> set[str]:
        # Run validation again, without the limit this time
        error = CreateSoundStripWithSound.disabled_reason(context, 0)
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
        strips = find_strips_of_sound(context)
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
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def disabled_reason(cls, context: Context, limit=poll_search_limit) -> str:
        error_common = CaptureProperties.sound_selection_validation(context, False)
        if error_common:
            return error_common
        strip = find_strips_of_sound(context, limit)
        if not strip:
            return f"No strip using the current sound found."
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def execute(self, context: Context) -> set[str]:
        error = self.disabled_reason(context, 0)  # Run validation again, without the limit this time
        if error:
            self.report({"ERROR"}, error)
            return {'CANCELLED'}
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound
        strips = find_strips_of_sound(context)
        assert strips
        if len(strips) > 1:
            m = f"There is more than one sound strips using the sound with '{sound.filepath}'. Don't know which one to remove."
            self.report({"ERROR"}, m)
            return {'CANCELLED'}
        se = context.scene.sequence_editor
        se.sequences.remove(strips[0])
        return {'FINISHED'}


class ToggleRelativePath(bpy.types.Operator):
    """Conver the sound path to absolute/relative"""

    bl_idname = "rhubarb.toggle_relative_path"
    bl_label = "Relative/Absolute"

    relative: BoolProperty(name="relative", description="Whether to convert to relative or absolute path")  # type: ignore

    @classmethod
    def description(csl, context: Context, self: 'ToggleRelativePath') -> str:
        return f"Convert to {'relative' if self.relative else 'absolute' } path"

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, CaptureProperties.sound_selection_validation)

    def get_converted(self, sound: Sound) -> str:
        if self.relative:
            return ui_utils.to_relative_path(sound.filepath)
        else:
            return ui_utils.to_abs_path(sound.filepath)

    def execute(self, context: Context) -> set[str]:
        props = CaptureProperties.from_context(context)
        sound: Sound = props.sound
        old = sound.filepath
        sound.filepath = self.get_converted(sound)
        if old == sound.filepath:
            self.report({'INFO'}, f"Unchanged")
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
            this.target_folder = bpy.path.abspath(props.sound_file_folder)
        this.target_filename = props.get_sound_name_with_new_extension(this.codec)

    @classmethod
    def description(csl, context: Context, self: 'ConvertSoundFromat') -> str:
        return f"Convert the selected sound to {self.codec}"

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, CaptureProperties.sound_selection_validation)

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

        if not RemoveSoundStripWithSound.disabled_reason(context):
            box = layout.box()
            box.label(text="Sound already used in the sequencer")
            box.operator(RemoveSoundStripWithSound.bl_idname, icon='MUTE_IPO_OFF')
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
        self.report({'INFO'}, f"Saving {self.target_path_full}")
        try:
            bpy.context.window.cursor_set("WAIT")
            asound.write(**args)
        finally:
            bpy.context.window.cursor_set("DEFAULT")
        # Open the newly created ogg/wav file
        ret = bpy.ops.sound.open(filepath=str(self.target_path_full))
        if not 'FINISHED' in ret:
            self.report({'WARNING'}, f"Failed to import and open the new file {self.target_path_full}")
            return {'FINISHED'}
        new_sounds = find_sounds_by_path(str(self.target_path_full))
        if not new_sounds:
            self.report({'WARNING'}, f"Failed to select the new file. The {self.target_path_full} not found in the sound datablocks")
            return {'FINISHED'}
        props.sound = new_sounds[0]
        return {'FINISHED'}


class PlayRange(bpy.types.Operator):
    """Starts animation playback from the current frame and stops automatically after played certain number of frames."""

    bl_idname = "rhubarb.play_range"
    bl_label = "Play and Stop"

    play_frames: IntProperty(name="Frames", description="Number of frames to play", default=10)  # type: ignore
    start_frame: IntProperty(name="Start", description="Frame to jump to prior playing", default=-1)  # type: ignore
    # restore_frame: BoolProperty(name="Restore frame", description="Jump back to the start frame after playback is done")  # type: ignore
    frames_left = 0

    @staticmethod
    def on_frame(scene):
        if log.isEnabledFor(logging.TRACE):
            log.trace(f"On frame {PlayRange.frames_left}")
        PlayRange.frames_left -= 1
        if PlayRange.frames_left <= 0:
            log.trace("Stopping playback. Counter reached zero.")
            try:
                bpy.ops.screen.animation_cancel(restore_frame=False)
            except:
                log.error(f"Failed to stop animation playback")
                traceback.print_exception()
            if not PlayRange.remove_handlers():
                log.warn(
                    f"""Coulnd't remove handler {ui_utils.func_fqname(PlayRange.on_frame)}. 
                        Handler not found:\n{bpy.app.handlers.frame_change_post}"""
                )

    @staticmethod
    def remove_handlers():
        try:
            # print(list(bpy.app.handlers.frame_change_post))
            fn = PlayRange.on_frame
            handlers = bpy.app.handlers.frame_change_post
            return ui_utils.remove_handler(handlers, PlayRange.on_frame)
        except:
            log.error(f"Unexpected error while stopping the animation")
            traceback.print_exception()
            return False

    @classmethod
    def disabled_reason(cls, context: Context, limit=0) -> str:
        # if getattr(context.screen, 'is_animation_playing', False):
        #    return f"Animation is playing. Counter:{PlayRange.frames_left}"
        # if self.pl
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def execute(self, context: Context) -> set[str]:
        PlayRange.frames_left = self.play_frames
        log.debug(f"Starting animation playback from {self.start_frame} frame. Frames to play: {self.play_frames}.")
        PlayRange.remove_handlers()
        if self.start_frame >= 0:
            context.scene.frame_set(frame=self.start_frame, subframe=0)

        if not getattr(context.screen, 'is_animation_playing', False):
            bpy.ops.screen.animation_play()  # Another play call would stop the playback if already playing
        else:
            log.trace("Animation is already playing.")  # type: ignore
        bpy.app.handlers.frame_change_post.append(PlayRange.on_frame)
        return {'FINISHED'}
