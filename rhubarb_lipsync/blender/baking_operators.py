import logging
import textwrap

import bpy
from bpy.props import BoolProperty, EnumProperty
from bpy.types import Context, Object, UILayout

from .. import IconsManager
from ..rhubarb.mouth_cues import MouthCue, frame2time, time2frame_float
from . import baking_utils, ui_utils
from .capture_properties import CaptureListProperties, CaptureProperties, ResultLogListProperties
from .mapping_operators import StopAllPreview
from .mapping_properties import MappingProperties
from .preferences import CueListPreferences, RhubarbAddonPreferences, StripPlacementPreferences

log = logging.getLogger(__name__)


def time_frame_predefined_vals(ctx: Context, times: list[float], frames: list[float]) -> list[tuple[str, str, str, str, int]]:
    fps = ctx.scene.render.fps
    fps_base = ctx.scene.render.fps_base
    frame_vals = [(frame2time(f, fps, fps_base) * 1000, f, "SNAP_INCREMENT") for f in frames]
    mss = [(s, time2frame_float(s / 1000, fps, fps_base), "TIME") for s in times]
    vals = frame_vals + mss

    def fields(i: int, ms: float, frame: float, ico: str) -> tuple[str, str, str, str, int]:
        return (f"{frame}", f"{ms:02}ms ({frame:0.2f} frame_vals)", "", ico, i)

    return [fields(i, int(v[0]), v[1], v[2]) for i, v in enumerate(vals)]


class RemoveCapturedNlaStrips(bpy.types.Operator):
    """Remove NLA Strips on bake-selected NLA Tracks on a given frame range. Making room for another bake."""

    bl_idname = "rhubarb.remove_captured_nla_strips"
    bl_label = "Remove strips"
    bl_options = {'UNDO'}

    # @classmethod
    # def disabled_reason(cls, ctx: Context) -> str:
    #     b = baking_utils.BakingContext(ctx)
    #     b.next_object()  # Only validate there is mapping for at least object
    #     print(b.current_object)
    #     return b.validate_selection()

    # @classmethod
    # def poll(cls, context: Context) -> bool:
    #     return ui_utils.validation_poll(cls, context)

    def on_track(self, bctx: baking_utils.BakingContext, track: bpy.types.NlaTrack) -> None:
        if not track:
            return
        self.tracks_cleaned += 1
        strips = list(bctx.strips_on_track(track))
        log.debug(f"Going to remove {len(strips)}")
        for strip in strips:
            track.strips.remove(strip)
            self.strips_removed += 1

    def on_object(self, bctx: baking_utils.BakingContext) -> None:
        log.debug(f"Removing strips from {bctx.current_object}")
        for t in bctx.unique_tracks:
            self.on_track(bctx, t)

    def execute(self, ctx: Context) -> set[str]:
        b = baking_utils.BakingContext(ctx)
        self.strips_removed = 0
        self.tracks_cleaned = 0
        if not b.objects:
            self.report({'ERROR'}, "No matching object in selection")
            return {'CANCELLED'}
        try:
            for o in b.object_iter():
                self.on_object(b)

        except Exception as e:
            self.report({'ERROR'}, str(e))
            log.exception(e)
            return {'CANCELLED'}
        self.report({'INFO'}, f"Removed {self.strips_removed} strips from {self.tracks_cleaned} tracks")
        return {'FINISHED'}


class PlacementBlendInOutRatioPreset(bpy.types.Operator):
    """Set the strip blend in/out ratio from the preconfigured values"""

    bl_idname = "rhubarb.placement_set_blendinout_ration"
    bl_label = "Set Blend in/out ratio from predefined values"
    bl_options = {'UNDO'}

    ratio_type: EnumProperty(  # type: ignore
        name="Scale preset",
        items=[
            ('0.2', '20% very quick blend in, very slow blend out', ""),
            ('0.4', '40% quick blend in, slow blend out', ""),
            ('0.5', '50% balanced blend in blend out', ""),
            ('0.6', '60% slow blend in, quick blend out', ""),
            ('0.8', '80% very slow blend in, very quick blend out', ""),
        ],
        default='0.5',
    )

    def execute(self, ctx: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        sprops: StripPlacementPreferences = prefs.strip_placement
        rate = float(self.ratio_type)
        sprops.blend_inout_ratio = rate
        return {'FINISHED'}


class PlacementScaleFromPreset(bpy.types.Operator):
    """Set the Blend In/Out value based on the strip Placement offsets"""

    bl_idname = "rhubarb.placement_set_scale"
    bl_label = "Set scale ranges from predefined values"
    bl_options = {'UNDO'}

    scale_type: EnumProperty(  # type: ignore
        name="Scale preset",
        items=[
            ('1', 'No scale', ""),
            ('1.1', 'Up to 10% difference', ""),
            ('1.25', 'Up to 25% difference', ""),
            ('1.50', 'Up to 50% difference', ""),
            ('1.75', 'Up to 75% difference', ""),
            ('2', 'Up to 100% difference', ""),
        ],
        default='1.25',
    )

    def execute(self, ctx: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        sprops: StripPlacementPreferences = prefs.strip_placement
        rate = float(self.scale_type)
        # sprops.scale_min = 2 - rate
        sprops.scale_min = 1 / rate
        sprops.scale_max = rate
        return {'FINISHED'}


class PlacementCueTrimFromPreset(bpy.types.Operator):
    """Set the cue trim time/frames from the preconfigured values"""

    bl_idname = "rhubarb.placement_set_trim"
    bl_label = "Set cue trim from predefined values"
    bl_options = {'UNDO'}

    vals_frames = [3, 4, 5, 6]
    vals_times = [150, 200, 250, 300, 400, 500, 600]

    trim_preset: EnumProperty(  # type: ignore
        name="Blend in Preset",
        items=lambda _, ctx: time_frame_predefined_vals(
            ctx,
            PlacementCueTrimFromPreset.vals_times,
            PlacementCueTrimFromPreset.vals_frames,
        ),
    )

    def execute(self, ctx: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        clp: CueListPreferences = prefs.cue_list_prefs
        fps = ctx.scene.render.fps
        fps_base = ctx.scene.render.fps_base
        clp.highlight_long_cues = frame2time(float(self.trim_preset), fps, fps_base)
        return {'FINISHED'}


class ShowPlacementHelp(bpy.types.Operator):
    """Show a popup with cue type description."""

    bl_idname = "rhubarb.show_placement_help"
    bl_label = "Strip placement help"
    # tex: PointerProperty(type=bpy.types.Texture, name="tex")  # type: ignore

    @staticmethod
    def draw_popup(this: bpy.types.UIPopupMenu, context: Context) -> None:
        row = this.layout.row()

        img, tex = IconsManager.placement_help_image()
        # img=ShowPlacementHelp.this.img
        # row.template_image(img, "pixels", tex.image_user)
        # row.template_preview(tex, show_buttons=False)
        row.scale_y = 2
        row.scale_x = 3
        # row.template_icon(img.preview.icon_id, scale=20)
        # row = this.layout.row()
        row.template_image(tex, "image", tex.image_user)
        # row.label(text=f"{tex.image}")

    def execute(self, context: Context) -> set[str]:
        # self.tex=tex
        img, tex = IconsManager.placement_help_image()
        img.preview_ensure()
        sp = ' ' * 200
        context.window_manager.popup_menu(ShowPlacementHelp.draw_popup, title=f"String placement settings help{sp}", icon="QUESTION")
        return {'FINISHED'}


class BakeToNLA(bpy.types.Operator):
    """Bake the selected objects to nla tracks"""

    bl_idname = "rhubarb.bake_to_nla"
    bl_label = "Bake to NLA"
    trim_cue_excess: BoolProperty(  # type: ignore
        name="Trim excess Cue length",
        description=textwrap.dedent(
            """\
            For detected Cues which are longer that the max Cue duration from preferences trim the excess length.  
            The gaps created by trimming are filled with the X shape. 
            """
        ),
        default=True,
    )

    preview_mapping_action: EnumProperty(  # type: ignore
        name="Preview Mapping Action",
        description="Determines how to handle preview mapping action when baking.",
        items=[
            ("MANUAL", "Manually using Preview button", "Preview mapping action manually when button is pressed."),
            ("AUTO", "Automatically after Ok button is pressed", "Automatically preview mapping action before new bake."),
        ],
        default="MANUAL",
    )

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        error_common = CaptureProperties.sound_selection_validation(context, False, False)
        if error_common:
            return error_common
        error_common = MappingProperties.context_selection_validation(context)
        if error_common:
            return error_common
        CaptureListProperties.capture_from_context(context)
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def invoke(self, context: Context, event: bpy.types.Event) -> set:
        # Open dialog

        rll: ResultLogListProperties = CaptureListProperties.from_context(context).last_resut_log
        rll.clear()  # Clear log entries from last bake
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=480)

    def to_strip(self) -> None:
        b = self.bctx
        cf = b.current_cue
        cue: MouthCue = cf and cf.cue or None
        if not b.current_mapping_action:
            with b.rlog.check_dups() as log:
                log.warning(f"There is no mapping for the cue {cue.key} in the capture. Ignoring", self.bctx.current_traceback)
            return

        # start = cue_frames.pre_start_frame_float  # The clip starts slightly before the cue start driven by the blend-in value

        bir: float = b.strip_placement_props.blend_inout_ratio
        prev_cf = b.preceding_cue

        if b.cue_processor.is_cue_silence(prev_cf) or b.strip_placement_props.inout_blend_type == "NO_BLENDING":
            # When the previous cue is silence, this cue should blend-in without overlap
            start = cf.start_frame_float
            blend_in = cf.get_middle_start_frame(bir) - start
        else:
            # The clip starts (blending in) after the end of the middle section of the previous clip.
            start = prev_cf.get_middle_end_frame_float(bir)
            blend_in = cf.get_middle_start_frame(bir) - start

        next_cf = b.following_cue
        if b.cue_processor.is_cue_silence(next_cf) or b.strip_placement_props.inout_blend_type == "NO_BLENDING":
            # When the following cue is silence, this cue should blend out without overlap
            end = cf.end_frame_float
            blend_out = cf.end_frame_float - cf.get_middle_end_frame_float(bir)
        else:
            end = next_cf.get_middle_start_frame(bir)
            blend_out = end - cf.get_middle_end_frame_float(bir)

        desired_strip_duration = end - start
        assert desired_strip_duration > 0, f"desired_strip_duration={desired_strip_duration} [{b.current_traceback}]"
        assert blend_in >= 0, f"blend_in={blend_in} [{b.current_traceback}]"
        assert blend_out >= 0, f"blend_out={blend_out} [{b.current_traceback}]"
        # Try to scale the strip to the cue duration
        scale = b.current_mapping_action_scale(desired_strip_duration)

        self.place_strip(start, end, blend_in, blend_out, scale)

    def place_strip(self, start: float, end: float, blend_in: float, blend_out: float, scale: float):
        b = self.bctx
        cf = b.current_cue
        cue: MouthCue = cf and cf.cue or None
        # Crop the previous strip-end to make room for the current strip start (if needed)
        if baking_utils.trim_strip_end_at(b.current_track, start):
            b.rlog.warning("Had to trim previous strip to make room for this one", self.bctx.current_traceback)
        # Create new strip. Start frame is mandatory but int only, so round it up to avoid clashing with previous one because of rouding error
        name = f"{cue.info.key_displ}.{str(b.cue_index).zfill(3)}"
        strip = b.current_track.strips.new(name, int(start + 1), b.current_mapping_action)
        if b.current_mapping_item.custom_frame_ranage:
            strip.action_frame_start = b.current_mapping_item.frame_start
            strip.action_frame_end = b.current_mapping_item.frame_end
        strip.frame_start = start  # Set start frame again as float (ctor takes only int)
        strip.scale = scale
        # if b.ctx.scene.show_subframe:
        strip.frame_end = end
        self.strips_added += 1
        strip.name = name
        strip.blend_type = b.strip_placement_props.strip_blend_type
        strip.extrapolation = b.strip_placement_props.extrapolation
        strip.use_sync_length = b.strip_placement_props.use_sync_length
        # Autoblend when forced by option, otherwise only autobled the silence cues (X or A)
        auto_blend = b.cue_processor.is_cue_silence(cf)  # Silence auto-blend by default
        if b.strip_placement_props.inout_blend_type == "ALWAYS_AUTOBLEND":
            auto_blend = True  # Auto-blend is forced
        if b.strip_placement_props.inout_blend_type == "NO_BLENDING":
            auto_blend = False  # Auto-blend disabled for all (even silence)

        if auto_blend:
            strip.use_auto_blend = True
            strip.frame_end = strip.frame_end - 0.001  # To avoid strips touching, which would effectivelly disable autoblend
        else:
            # No autoblending
            if b.strip_placement_props.inout_blend_type == "BY_RATIO":
                strip.blend_in = blend_in
                strip.blend_out = blend_out

    def bake_cue_on_object(self, obj: Object) -> None:
        b = self.bctx

        track = b.current_track
        if not track:
            if b.cue_index <= 0:  # Only log the error 1x
                b.rlog.error(f"{obj and obj.name} has no NLA track selected. Ignoring", self.bctx.current_traceback)
            return
        self.to_strip()

    def bake_cue(self) -> None:
        for obj in self.bctx.object_iter():
            assert self.bctx.current_cue, "No cue selected"
            # print(self.bctx.cue_index)
            if log.isEnabledFor(logging.TRACE):  # type: ignore
                log.trace(f"Baking on object {obj} ")  # type: ignore
            self.bake_cue_on_object(obj)

    def execute(self, ctx: Context) -> set[str]:
        self.bctx = baking_utils.BakingContext(ctx)
        self.strips_added = 0
        b = self.bctx

        # Check strip removal mode and perform auto-removal if needed
        prefs = RhubarbAddonPreferences.from_context(ctx)
        if prefs.strip_removal_mode == "AUTO":
            log.info("Auto-removing existing NLA strips before baking")
            bpy.ops.rhubarb.remove_captured_nla_strips()
        if prefs.stop_preview_mode == "AUTO":
            bpy.ops.rhubarb.stop_all_preview()

        wm = ctx.window_manager
        l = len(b.mouth_cue_items)
        log.info(f"About to optimize {l} cues")
        wm.progress_begin(0, l)
        try:
            b.optimize_cues()
            # Loop over cues and for each cue alternate between the two tracks and for each track loop over all objects
            log.debug("Optimization done. Placing NLA strips")
            for i, cue_frames in enumerate(b.cue_iter()):
                # print(b.cue_index)
                wm.progress_update(i)
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Baking cue {cue_frames.cue} ({i}/{l}) ")
                self.bctx.next_track()
                self.bake_cue()

            msg = f"Baked {l} cues to {self.strips_added} action strips"
            self.bctx.rlog.info(msg, self.bctx.current_traceback)
            self.report({'INFO'}, msg)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            log.exception(e)
            self.bctx.rlog.error(str(e), self.bctx.current_traceback)
            return {'CANCELLED'}
        finally:
            del self.bctx
            ui_utils.redraw_3dviews(ctx)

        return {'FINISHED'}

    def draw_error_inbox(self, l: UILayout, text: str) -> None:
        ui_utils.draw_error(l, text, False)

    def draw_info(self) -> None:
        b = self.bctx

        # Redundant validations to allow collapsing this sub-panel while still indicating any errors
        selected_objects = list(b.mprefs.object_selection_filtered(b.ctx))

        errors = not b.cprops or not b.mouth_cue_items or not selected_objects or not b.objects
        if not ui_utils.draw_expandable_header(b.prefs, "bake_info_panel_expanded", "Selection Info", self.layout, errors):
            return

        # layout.prop(rootProps, 'name', text="")

        box = self.layout.box().column(align=True)
        line = box.split()
        line.label(text="Mouth cues")
        if b.mouth_cue_items:
            line.label(text=str(len(b.mouth_cue_items)))
        else:
            self.draw_error_inbox(line, "No cues")

        line = box.split()
        line.label(text="Objects selected")

        if selected_objects:
            line.label(text=f"{len(selected_objects)}")
        else:
            self.draw_error_inbox(line, "None")

        objs_to_bake = b.objects
        line = box.split()
        line.label(text="Objects with mapping")
        if len(objs_to_bake):
            line.label(text=f"{len(objs_to_bake)}")
        else:
            self.draw_error_inbox(line, "None of the selected")

    def draw_validation_msg(self, box: UILayout, msg: str) -> None:
        tag = None
        if "#!" in msg:  # Parse out UI tags from error message
            parts = msg.split("#!")
            msg = parts[0].strip()
            tag = parts[1].strip() if len(parts) > 1 else None

        # Display the error message without the tag

        if not tag:
            self.draw_error_inbox(box.row(), msg)
            return
        inner_box: UILayout = box.box()
        prefs = RhubarbAddonPreferences.from_context(self.bctx.ctx)
        col = inner_box.column(align=False)
        col.use_property_split = True

        def draw_dropdown(pref_key: str) -> UILayout:

            line = col.split()
            line.prop(prefs, pref_key)  # type: ignore
            return line

        # Add specific UI elements based on the tag
        if tag == "RemoveStrips":
            if prefs.strip_removal_mode == "MANUAL":
                self.draw_error_inbox(col.row(), msg)
                line = draw_dropdown("strip_removal_mode")
                line = col.split()
                line.operator(RemoveCapturedNlaStrips.bl_idname, text="Remove clashing strips now")
            else:
                col.row().label(text=msg)
                line = draw_dropdown("strip_removal_mode")

        if tag == "StopAction":

            if prefs.stop_preview_mode == "MANUAL":
                self.draw_error_inbox(col.row(), msg)
                line = draw_dropdown("stop_preview_mode")
                line = col.split()
                inner_box.operator(StopAllPreview.bl_idname, text="Stop preview")
            else:
                col.row().label(text=msg)
                line = draw_dropdown("stop_preview_mode")

    def draw_validation(self) -> None:
        b = self.bctx
        if not b.objects:
            return
        box = None
        for o in b.object_iter():
            errs = b.validate_current_object()

            if not errs:
                continue
            if not box:
                box = self.layout.box().column(align=True)
            box.separator()
            row = box.row()
            row.label(text=o.name)

            for e in errs:
                self.draw_validation_msg(box, e)

    def draw(self, ctx: Context) -> None:
        self.bctx = baking_utils.BakingContext(ctx)

        layout = self.layout
        rootProps = self.bctx.clist_props
        row = self.layout.row(align=True)
        row.prop(rootProps, 'name', text="Capture")  # type: ignore
        layout.separator()
        row = layout.row(align=False)
        row.prop(self.bctx.cprops, "start_frame")  # type: ignore
        if self.bctx.cue_processor.the_last_cue:
            row.label(text=f"End frame: {self.bctx.cue_processor.the_last_cue.end_frame_str}")
        layout.prop(self.bctx.mprefs, "object_selection_filter_type", text="Objects to bake")  # type: ignore
        self.draw_info()
        self.draw_validation()
