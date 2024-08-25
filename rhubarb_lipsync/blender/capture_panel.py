import logging
import pathlib

import bpy
from bpy.types import Context, Sound

from ..rhubarb import mouth_cues
from . import capture_operators, rhubarb_operators, sound_operators, ui_utils
from .capture_properties import CaptureListProperties, JobProperties, MouthCueList, MouthCueListItem
from .cue_uilist import MouthCueUIList
from .preferences import CueListPreferences, RhubarbAddonPreferences
from .ui_utils import IconsManager

log = logging.getLogger(__name__)


class CaptureExtraOptionsPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_capture_extra_options"
    bl_label = "RLPS: Additional capture options"
    bl_space_type = "PROPERTIES"
    bl_region_type = "HEADER"
    # bl_category = "RLPS"

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        props = CaptureListProperties.capture_from_context(context)

        layout = self.layout
        row = layout.row()
        row.label(text="Dialog File:")
        row = layout.row()
        row.prop(props, "dialog_file", text="")
        layout.separator()

        layout.prop(prefs, "use_extended_shapes")
        layout.separator()

        row = layout.row()
        row.label(text="Recognizer:")
        row = layout.row()
        row.prop(prefs, "recognizer", text="")


class CueListOptionsPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_cue_list_options"
    bl_label = "Cue list display options"
    bl_space_type = "PROPERTIES"
    bl_region_type = "HEADER"

    # bl_category = "RLPS"

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        o: CueListPreferences = prefs.cue_list_prefs
        layout = self.layout
        layout.label(text=CueListOptionsPanel.bl_label)
        layout.prop(context.scene, "show_subframe", text="Show subframes")
        for name in o.noncol_props_names:
            layout.prop(o, name)


class CueListColsVisibilityPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_cue_list_columns"
    bl_label = "Visible columns"
    bl_space_type = "PROPERTIES"
    bl_region_type = "HEADER"
    bl_parent_id = CueListOptionsPanel.bl_idname
    # bl_category = "RLPS"

    def draw(self, context: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(context)
        o: CueListPreferences = prefs.cue_list_prefs
        layout = self.layout
        for name in o.col_props_names:
            layout.prop(o, name)


class CaptureMouthCuesPanel(bpy.types.Panel):
    bl_idname = "RLPS_PT_capture"
    bl_label = "RLPS: Sound Setup and Cues Capture"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RLPS"
    # bl_parent_id= 'VIEW3D_PT_example_panel'
    # bl_description = "Tool tip"
    # bl_context = "object"

    @staticmethod
    def on_cuelist_index_changed(cueList: MouthCueList, ctx: Context, item: MouthCueListItem) -> None:
        # Even handler called when the cue list index changes in the properties.
        cp: CueListPreferences = RhubarbAddonPreferences.from_context(ctx).cue_list_prefs
        if not cp.sync_on_select:
            return
        frame, subframe = item.cue_frames(ctx).start_subframe
        ctx.scene.frame_set(frame=frame, subframe=subframe)

    MouthCueList.index_changed = on_cuelist_index_changed  # Register callback

    def draw_sound_setup(self) -> bool:
        props = CaptureListProperties.capture_from_context(self.ctx)
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        sound: Sound = props and props.sound

        # Redundant validations to allow collapsing this sub-panel while still indicating any errors
        if sound is None:
            errors = True
        else:
            path = pathlib.Path(sound.filepath)
            errors = not sound or sound.packed_file or not path.exists or not props.is_sound_format_supported()
        if not ui_utils.draw_expandable_header(prefs, "sound_source_panel_expanded", "Input Sound Setup", self.layout, errors):
            return not errors
        layout = self.layout

        if not props:
            ui_utils.draw_error(self.layout, "Select a capture.")
            return False
        layout.template_ID(props, "sound", open="sound.open")
        if sound is None:
            ui_utils.draw_error(self.layout, "Select a sound file.")
            return False

        row = layout.row(align=True)
        row.prop(sound, "filepath", text="")

        blid = sound_operators.ToggleRelativePath.bl_idname

        op = row.operator(blid, text="", icon="DOT").relative = True
        if props.sound_file_path and not props.sound_file_path.exists():
            absp = pathlib.Path(ui_utils.to_abs_path(sound.filepath))
            if absp.exists():
                row.alert = True

        op = row.operator(blid, text="", icon="ITALIC").relative = False

        row = layout.row(align=True)
        row.operator(sound_operators.CreateSoundStripWithSound.bl_idname, icon='SPEAKER').start_frame = props.start_frame
        row.operator(sound_operators.RemoveSoundStripWithSound.bl_idname, icon='MUTE_IPO_OFF')
        layout.prop(props, 'start_frame')
        layout.prop(self.ctx.scene, 'use_audio_scrub')
        layout.prop(self.ctx.scene, 'sync_mode')
        # bpy.context.scene.sync_mode = 'AUDIO_SYNC'

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
        props = CaptureListProperties.capture_from_context(self.ctx)
        prefs = RhubarbAddonPreferences.from_context(self.ctx)

        if not ui_utils.draw_expandable_header(prefs, "info_panel_expanded", "Additional Info", self.layout):
            return
        box = self.layout.box().column(align=True)
        # line = layout.split()
        if props and props.sound:
            sound: Sound = props.sound
            line = box.split()
            line.label(text="Sample Rate")
            line.label(text=f"{sound.samplerate} Hz")
            line = box.split()
            line.label(text="Channels")
            line.label(text=str(sound.channels))

            line = box.split()
            line.label(text="File Extension")
            line.label(text=props.sound_file_extension)
            box.separator()
        line = box.split()
        line.label(text="Rhubarb Version")
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
            # https://blender.stackexchange.com/questions/211184/how-to-tag-a-redraw-in-all-viewports
            # self.ctx.area.tag_redraw()  # Force redraw
            ui_utils.redraw_3dviews(self.ctx)
            f = self.ctx.scene.frame_current_final
            t = mouth_cues.frame2time(f, self.ctx.scene.render.fps, self.ctx.scene.render.fps_base)
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
        props = CaptureListProperties.capture_from_context(self.ctx)
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

    def draw_capture_toolbar(self) -> None:
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        cpref: CueListPreferences = prefs.cue_list_prefs

        row = self.layout.row()

        toolRow = row.row(align=True)
        toolRow.prop(cpref, 'preview', icon="UV_SYNC_SELECT", icon_only=True)
        toolRow.prop(cpref, 'sync_on_select', icon="RESTRICT_SELECT_OFF", icon_only=True)

        actionRow = row.row(align=True)
        actionRow.label(text="")  # Spacer to force icons alight to the right
        actionRow.operator(capture_operators.ExportCueList2Json.bl_idname, text="", icon="EXPORT")
        actionRow.operator(capture_operators.ImportJsonCueList.bl_idname, text="", icon="IMPORT")
        actionRow.popover(panel=CueListOptionsPanel.bl_idname, text="", icon="VIS_SEL_11")
        actionRow.operator(capture_operators.ClearCueList.bl_idname, text="", icon="PANEL_CLOSE")

    def draw_capture(self) -> None:
        prefs = RhubarbAddonPreferences.from_context(self.ctx)
        props = CaptureListProperties.capture_from_context(self.ctx)
        if not props:
            return
        jprops: JobProperties = props.job

        title = self.get_job_status_title(jprops.status)
        error = bool(jprops.error)

        if not ui_utils.draw_expandable_header(prefs, "caputre_panel_expanded", title, self.layout, error):
            return

        self.draw_job()
        self.draw_capture_toolbar()

        list_type = 'GRID' if prefs.cue_list_prefs.as_grid else 'DEFAULT'
        lst: MouthCueList = props.cue_list
        self.layout.template_list(MouthCueUIList.bl_idname, "Mouth cues", lst, "items", lst, "index", type=list_type)

    def draw(self, context: Context) -> None:
        try:
            self.ctx = context
            layout = self.layout
            # layout.use_property_split = True
            # layout.use_property_decorate = False  # No animation.

            # selection_error = MappingProperties.context_selection_validation(context)
            # if selection_error:
            #     ui_utils.draw_error(self.layout, selection_error)
            # else:
            # , open="sound.open"
            # layout.template_list(props, "items")
            # https://devtalk.blender.org/t/prop-search-with-activate-init/28887/3R
            rootProps = CaptureListProperties.from_context(context)
            # layout.prop_search(rootProps.items)
            # layout.prop_search()
            # row.prop_search(scene.keying_sets, "active", scene, "keying_sets", text="")
            # layout.template_list(rootProps, "items")
            # layout.template_ID(rootProps, "items")
            # layout.template_search(rootProps, 'items')
            if rootProps.items:
                row = layout.row(align=True)
                row.prop(rootProps, 'name', text="")
                # row.prop(rootProps, 'index', text="")
                row.operator(capture_operators.CreateCaptureProps.bl_idname, text="", icon="DUPLICATE")
                row.operator(capture_operators.DeleteCaptureProps.bl_idname, text="", icon="PANEL_CLOSE")
            else:
                layout.operator(capture_operators.CreateCaptureProps.bl_idname, icon="DUPLICATE")

            self.draw_sound_setup()
            self.draw_info()

            self.draw_capture()

        except Exception as e:
            ui_utils.draw_error(self.layout, f"Unexpected error. \n {e}")
            raise
        finally:
            self.ctx = None
