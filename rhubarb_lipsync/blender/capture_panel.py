import logging
import pathlib
from io import TextIOWrapper
from typing import Dict, List, Optional, cast

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, Sound, SoundSequence

import rhubarb_lipsync.blender.rhubarb_operators as rhubarb_operators
import rhubarb_lipsync.blender.sound_operators as sound_operators
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences, CueListPreferences
from rhubarb_lipsync.blender.properties import CaptureProperties, MouthCueList, MouthCueListItem, JobProperties
from rhubarb_lipsync.blender.ui_utils import IconsManager
from rhubarb_lipsync.blender.cue_list import MouthCueUIList
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob
import rhubarb_lipsync.rhubarb.mouth_shape_data as shape_data

log = logging.getLogger(__name__)


class CaptureExtraOptionsPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_capture_extra_options"
    bl_label = "RLPS: Additional capture options"
    bl_space_type = "PROPERTIES"
    bl_region_type = "HEADER"
    # bl_category = "RLSP"

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        props = CaptureProperties.from_context(context)

        layout = self.layout
        layout.prop(props, "dialog_file")
        layout.prop(prefs, "use_extended_shapes")


class CueListOptionsPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_cue_list_options"
    bl_label = "Cue list display options"
    bl_space_type = "PROPERTIES"
    bl_region_type = "HEADER"

    # bl_category = "RLSP"

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        o: CueListPreferences = prefs.cue_list_prefs
        layout = self.layout
        layout.label(text=CueListOptionsPanel.bl_label)
        for name in o.noncol_props_names:
            layout.prop(o, name)


class CueListColsVisibilityPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_cue_list_columns"
    bl_label = "Visible columns"
    bl_space_type = "PROPERTIES"
    bl_region_type = "HEADER"
    bl_parent_id = CueListOptionsPanel.bl_idname
    # bl_category = "RLSP"

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        o: CueListPreferences = prefs.cue_list_prefs
        layout = self.layout
        for name in o.col_props_names:
            layout.prop(o, name)


class CaptureMouthCuesPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_capture"
    bl_label = "RLPS: Sound setup and cues capture"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RLSP"
    # bl_parent_id= 'VIEW3D_PT_example_panel'
    # bl_description = "Tool tip"
    # bl_context = "object"

    @staticmethod
    def on_cuelist_index_changed(cueList: MouthCueList, ctx: Context, item: MouthCueListItem) -> None:
        # Even handler called when the cue list index changes in the properties.
        cp: CueListPreferences = RhubarbAddonPreferences.from_context(ctx).cue_list_prefs
        if not cp.sync_on_select:
            return
        frame, subframe = item.subframe(ctx)
        ctx.scene.frame_set(frame=frame, subframe=subframe)

    MouthCueList.index_changed = on_cuelist_index_changed  # Register callback

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
        layout.template_ID(props, "sound", open="sound.open")
        if sound is None:
            ui_utils.draw_error(self.layout, "Select a sound file.")
            return False
        row = layout.row(align=True)
        row.prop(sound, "filepath", text="")

        blid = sound_operators.ToggleRelativePath.bl_idname

        op = row.operator(blid, text="", icon="DOT").relative = True
        if not props.sound_file_path.exists():
            absp = pathlib.Path(ui_utils.to_abs_path(sound.filepath))
            if absp.exists():
                row.alert = True

        op = row.operator(blid, text="", icon="ITALIC").relative = False

        row = layout.row(align=True)
        row.operator(sound_operators.CreateSoundStripWithSound.bl_idname, icon='SPEAKER')
        row.operator(sound_operators.RemoveSoundStripWithSound.bl_idname, icon='MUTE_IPO_OFF')
        layout.prop(self.ctx.scene, 'use_audio_scrub')
        if sound:
            layout.prop(sound, "use_memory_cache")

        if sound.packed_file:
            ui_utils.draw_error(self.layout, "Rhubarb requires the file on disk.\n Please unpack the sound.")
            unpackop = layout.operator("sound.unpack", icon='PACKAGE', text=f"Unpack '{sound.name}'")
            unpackop.id = sound.name_full  # type: ignore
            unpackop.method = 'USE_ORIGINAL'  # type: ignore
            return False

        if not path.exists:
            ui_utils.draw_error(self.layout, "Sound file doesn't exist.")
            return False

        convert = False

        if sound.samplerate < 16 * 1000:
            ui_utils.draw_error(self.layout, "Only samplerate >16k supported")
            convert = True

        if not props.is_sound_format_supported():
            ui_utils.draw_error(self.layout, "Only wav or ogg supported.")
            convert = True

        if convert or prefs.always_show_conver:
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

    def draw_info(self) -> None:
        props = CaptureProperties.from_context(self.ctx)
        prefs = RhubarbAddonPreferences.from_context(self.ctx)

        if not ui_utils.draw_expandable_header(prefs, "info_panel_expanded", "Additional info", self.layout):
            return
        box = self.layout.box().column(align=True)
        # line = layout.split()
        if props and props.sound:
            sound: Sound = props.sound
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
        r = self.ctx.scene.render

        line.label(text=f"{r.fps/r.fps_base:0.2f}")

    def get_job_status_title(self, status: str) -> str:
        if not status:
            return "Capture"
        return f"Capture ({status})"

    def get_cue_icon(self, cue_list: MouthCueList) -> int:
        # When animation is running follow the icon from the cue list=> preview
        cp: CueListPreferences = RhubarbAddonPreferences.from_context(self.ctx).cue_list_prefs
        if getattr(self.ctx.screen, 'is_animation_playing', False) and cp.preview:
            self.ctx.area.tag_redraw()  # Force redraw
            f = self.ctx.scene.frame_current_final
            t = shape_data.fram2time(f, self.ctx.scene.render.fps, self.ctx.scene.render.fps_base)
            cue = cue_list.find_cue_by_time(t)
            if cue:  # Time resolved to a cue, show its icon
                return IconsManager.cue_icon(cue.key)
            return IconsManager.cue_icon('X')  # No matching cue, show X
        # When stopped use the icon from the selected cue
        if cue_list.selected_item:
            return IconsManager.cue_icon(cue_list.selected_item.key)
        # If nothing selected (empty) use the default icon
        return IconsManager.logo_icon()

    def draw_job(self) -> None:
        props = CaptureProperties.from_context(self.ctx)
        jprops: JobProperties = props.job
        cue_list: MouthCueList = props.cue_list
        layout = self.layout

        title = self.get_job_status_title(jprops.status)
        row = layout.row(align=True)

        # box = row.box()
        # box.template_icon(icon_value=ico, scale=1.5)
        ico = self.get_cue_icon(cue_list)
        row.template_icon(icon_value=ico, scale=2.5)

        row = row.row(align=True)
        row.scale_y = 2
        row.operator(rhubarb_operators.ProcessSoundFile.bl_idname, text=title)
        row.popover(panel=CaptureExtraOptionsPanel.bl_idname, text="", icon="DOWNARROW_HLT")

        if jprops.running:
            row = layout.row(align=True)
            r = row.row(align=True)
            r.enabled = False
            r.prop(jprops, "progress", text="Progress", slider=True)
            r = row.row(align=True)
            r.enabled = not jprops.cancel_request
            r.prop(jprops, "cancel_request", text="", icon="PANEL_CLOSE")
        if jprops.error:
            ui_utils.draw_error(layout, jprops.error)

    def draw_capture(self) -> None:
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        cpref: CueListPreferences = prefs.cue_list_prefs
        props = CaptureProperties.from_context(self.ctx)
        if not props:
            return
        jprops: JobProperties = props.job

        title = self.get_job_status_title(jprops.status)
        error = bool(jprops.error)

        if not ui_utils.draw_expandable_header(prefs, "caputre_panel_expanded", title, self.layout, error):
            return

        self.draw_job()
        lst: MouthCueList = props.cue_list

        layout = self.layout

        row = layout.row(align=False)
        row.alignment = 'RIGHT'
        toolRow = row.row(align=True)
        toolRow.prop(cpref, 'preview', icon="UV_SYNC_SELECT", icon_only=True)
        toolRow.prop(cpref, 'sync_on_select', icon="RESTRICT_SELECT_OFF", icon_only=True)

        toolRow.enabled = bool(lst.items)
        row.popover(panel=CueListOptionsPanel.bl_idname, text="", icon="VIS_SEL_11")
        row.operator(rhubarb_operators.ClearCueList.bl_idname, text="", icon="PANEL_CLOSE")

        list_type = 'GRID' if prefs.cue_list_prefs.as_grid else 'DEFAULT'
        layout.template_list(MouthCueUIList.bl_idname, "Mouth cues", lst, "items", lst, "index", type=list_type)

    def draw(self, context: Context) -> None:
        try:
            props = CaptureProperties.from_context(context)
            self.ctx = context
            layout = self.layout
            # layout.use_property_split = True
            # layout.use_property_decorate = False  # No animation.

            selection_error = CaptureProperties.context_selection_validation(context)
            if selection_error:
                ui_utils.draw_error(self.layout, selection_error)
            else:
                self.draw_sound_setup()
            self.draw_info()

            self.draw_capture()

        except Exception as e:
            ui_utils.draw_error(self.layout, f"Unexpected error. \n {e}")
            raise
        finally:
            self.ctx = None
