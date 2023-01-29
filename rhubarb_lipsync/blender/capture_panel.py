from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context, Sound, SoundSequence

from typing import Optional, List, Dict, cast
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty, IntProperty
from rhubarb_lipsync.blender.properties import CaptureProperties, RhubarbAddonPreferences, IconsManager
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

    def draw_sound_setup(self) -> bool:
        props = CaptureProperties.from_context(self.ctx)
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        sound: Sound = props.sound

        # Redundant validations to allow collapsing this sub-panel while still indicating any errors
        if sound is None:
            errors = True
        else:
            path = pathlib.Path(sound.filepath)
            errors = sound.packed_file or not path.exists or not props.is_sound_format_supported()
        if not ui_utils.draw_expandable_header(prefs, "sound_source_panel_expanded", "Input sound setup", self.layout, errors):
            return not errors

        layout = self.layout
        layout.template_ID(props, "sound", open="sound.open")  # type: ignore
        if sound is None:
            ui_utils.draw_error(self.layout, "Select a sound file.")
            return False
        layout.prop(sound, "filepath", text="")  # type: ignore
        row = layout.row(align=True)
        blid = sound_operators.ToggleRelativePath.bl_idname
        op = row.operator(blid, text="Relative").relative = True
        op = row.operator(blid, text="Absolute").relative = False

        row = layout.row(align=True)
        row.operator(sound_operators.CreateSoundStripWithSound.bl_idname, icon='SPEAKER')
        row.operator(sound_operators.RemoveSoundStripWithSound.bl_idname, icon='MUTE_IPO_OFF')

        if sound.packed_file:
            ui_utils.draw_error(self.layout, "Rhubarb requires the file on disk.\n Please unpack the sound.")
            unpackop = layout.operator("sound.unpack", icon='PACKAGE', text=f"Unpack '{sound.name}'")
            unpackop.id = sound.name_full  # type: ignore
            unpackop.method = 'USE_ORIGINAL'  # type: ignore
            return False

        if not path.exists:
            ui_utils.draw_error(self.layout, "Sound file doesn't exist.")
            return False

        if not props.is_sound_format_supported():
            ui_utils.draw_error(self.layout, "Only wav or ogg supported.")
            row = layout.row(align=True)
            row.label(text="Convert to")
            blid = sound_operators.ConvertSoundFromat.bl_idname

            op = row.operator(blid, text="ogg")
            op.codec = 'ogg'  # type: ignore
            sound_operators.ConvertSoundFromat.init_props_from_sound(op, self.ctx)

            op = row.operator(blid, text="wav")
            op.codec = 'wav'  # type: ignore
            sound_operators.ConvertSoundFromat.init_props_from_sound(op, self.ctx)

            return False

        return True

    def draw_info(self):
        props = CaptureProperties.from_context(self.ctx)
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        sound: Sound = props.sound
        if not ui_utils.draw_expandable_header(prefs, "info_panel_expanded", "Additional info", self.layout):
            return
        box = self.layout.box()
        # line = layout.split()
        if sound:
            line = box.split()
            line.label(text="Sample rate")
            line.label(text=f"{sound.samplerate} Hz")
            line = box.split()
            line.label(text="Channels")
            line.label(text=str(sound.channels))

            line = box.split()
            line.label(text="File extension")
            line.label(text=props.sound_file_extension)
            box.separator()
        line = box.split()
        line.label(text="Rhubarb version")
        ver = rhubarb_operators.GetRhubarbExecutableVersion.get_cached_value(self.ctx)
        if ver:  # Cached value, just show
            line.label(text=ver)
        else:  # Not cached, offer button
            line.operator(rhubarb_operators.GetRhubarbExecutableVersion.bl_idname)

        line = box.split()
        line.label(text="FPS")
        line.label(text=f"{self.ctx.scene.render.fps}")

    def draw(self, context: Context):
        try:
            self.ctx = context
            layout = self.layout
            selection_error = CaptureProperties.context_selection_validation(context)
            if selection_error:
                ui_utils.draw_error(self.layout, selection_error)
                return

            # layout.prop(self.props, "sound")
            if not self.draw_sound_setup():
                self.draw_info()
                return
            self.draw_info()
            # layout.operator(rhubarb_operators.ProcessSoundFile.bl_idname, icon="MONKEY")
            layout.operator(rhubarb_operators.ProcessSoundFile.bl_idname, icon_value=IconsManager.get('rhubarb64x64'))

        except Exception as e:
            ui_utils.draw_error(self.layout, f"Unexpected error. \n {e}")
            raise
        finally:
            self.ctx = None  # type: ignore
