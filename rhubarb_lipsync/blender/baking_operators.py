import logging
import re
import bpy
from bpy.props import EnumProperty
from bpy.types import AlphaUnderSequence, Context, ImageUser, Object, UILayout

from rhubarb_lipsync.blender.preferences import CueListPreferences
from rhubarb_lipsync.blender.ui_utils import IconsManager
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, ResultLogListProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, StripPlacementProperties
import rhubarb_lipsync.blender.ui_utils as ui_utils
import rhubarb_lipsync.blender.baking_utils as baking_utils
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from rhubarb_lipsync.rhubarb.rhubarb_command import MouthCue

log = logging.getLogger(__name__)


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

    def on_track(self, bctx: baking_utils.BakingContext) -> None:
        track = bctx.current_track
        if not track:
            return
        self.tracks_cleaned += 1
        strips = list(bctx.strips_on_current_track())
        log.debug(f"Going to remove {len(strips)}")
        for strip in strips:
            track.strips.remove(strip)
            self.strips_removed += 1

    def on_object(self, bctx: baking_utils.BakingContext) -> None:
        log.debug(f"Removing strips from {bctx.current_object}")
        bctx.next_track()
        self.on_track(bctx)
        if bctx.has_two_tracks:
            bctx.next_track()
            self.on_track(bctx)

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


class PlacementScaleFromPreset(bpy.types.Operator):
    """Set the Blend In/Out value based on the strip Placement offsets"""

    bl_idname = "rhubarb.placement_set_scale"
    bl_label = "Set scale ranges from predefined value"
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
        mprops: MappingProperties = MappingProperties.from_context(ctx)
        sprops: StripPlacementProperties = mprops.strip_placement
        rate = float(self.scale_type)
        # sprops.scale_min = 2 - rate
        sprops.scale_min = 1 / rate
        sprops.scale_max = rate
        return {'FINISHED'}


class PlacementBlendInOutFromOverlap(bpy.types.Operator):
    """Set the placement scale value based on the preconfigured values"""

    bl_idname = "rhubarb.placement_set_blendinout"
    bl_label = "Set Blend In/Out from Offsets"
    bl_options = {'UNDO'}

    sync_type: EnumProperty(  # type: ignore
        name="Set blend in/out base on",
        items=[
            ('ZERO', 'in=0 out=0', "Zero blend in/out"),
            ('START_END', 'From Offset: in=start out=end', "Based on offset start and offset end"),
            ('OVERLAP', 'From Offset in=out=(end-start)', "Based on the overalp"),
        ],
        default='START_END',
    )

    def execute(self, ctx: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(ctx)
        sprops: StripPlacementProperties = mprops.strip_placement
        if self.sync_type == "ZERO":
            sprops.blend_in = 0
            sprops.blend_out = 0
        if self.sync_type == "START_END":
            sprops.blend_in = -sprops.offset_start
            sprops.blend_out = sprops.offset_end
        if self.sync_type == "OVERLAP":
            sprops.blend_in = sprops.overlap_length
            sprops.blend_out = sprops.overlap_length

        return {'FINISHED'}


class PlacementOffsetFromPreset(bpy.types.Operator):
    """Set the Offset  start/end value based on the predefined values"""

    offset_rx = re.compile(r"(?P<start>\d+\.?\d*),(?P<end>\d+\.?\d*)")

    bl_idname = "rhubarb.placement_set_offset"
    bl_label = "Set offsets from predefined value"
    bl_options = {'UNDO'}

    offset_type: EnumProperty(  # type: ignore
        name="Offset preset",
        items=[
            ('0,0', 'No offset', ""),
            ('0,1', '0.0 1.0', ""),
            ('0.5,1', '0.5 1.0', ""),
            ('0.5,2', '0.5 2.0', ""),
            ('1,1', '1.0 1.0', ""),
            ('1,1.5', '1.0 1.5', ""),
            ('1,2', '1.0 2.0', ""),
            ('1.5,1.5', '1.5 1.5', ""),
            ('1.5,2', '1.5 2', ""),
            ('1.5,2.5', '1.5 2.5', ""),
            ('1.5,3', '1.5 3', ""),
            ('2,3', '2 3', ""),
        ],
        default='1,2',
    )

    def execute(self, ctx: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(ctx)
        sprops: StripPlacementProperties = mprops.strip_placement
        rx = PlacementOffsetFromPreset.offset_rx
        m = re.search(rx, self.offset_type)
        assert m is not None, f"The {self.offset_type} doesn't match {rx}"
        start = float(m.groupdict()["start"])
        end = float(m.groupdict()["end"])
        sprops.offset_start = -start
        sprops.offset_end = end
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
        description="For detected Cues which are longer that the max Cue duration from preferences trim the excess length.",
        default=True,
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

    def invoke(self, context: Context, event: bpy.types.Event) -> set[int] | set[str]:
        # Open dialog

        rll: ResultLogListProperties = CaptureListProperties.from_context(context).last_resut_log
        rll.clear()  # Clear log entries from last bake
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=480)

    def to_strip(self) -> None:
        b = self.bctx
        cue_item = b.current_cue_item
        cue: MouthCue = cue_item and cue_item.cue or None
        if not b.current_mapping_action:
            b.rlog.warning(f"There is no mapping for the cue {cue} in the capture. Ignoring", self.bctx.current_traceback)
            return
        cue_frames = cue_item.cue_frames(b.ctx)
        name = f"{cue.info.key_displ}.{str(b.cue_index).zfill(3)}"

        # Shift the start frame
        start = cue_frames.start_frame_float + b.strip_placement_props.offset_start
        # Calculate the desired strip length based on cue length and include the offset
        desired_strip_duration = cue_frames.duration_frames_float + b.strip_placement_props.overlap_length
        # Try to scale the strip to the cue duration with the blendings included.
        scale = b.current_mapping_action_scale(desired_strip_duration)

        # Calculate the end frame based on the scale and the start. This is where the Action ends after the scaling (with offsets)
        # end = start + b.current_mapping_action_length_frames * scale
        # Set the strip end to the cue end (plus offset) no matter where the actual action ends.
        end = cue_frames.end_frame_float + b.strip_placement_props.offset_end

        # Crop the previous strip-end to make a room for the current strip start (if needed)
        if baking_utils.trim_strip_end_at(b.current_track, start):
            b.rlog.warning("Had to trim previous strip to make room for this one", self.bctx.current_traceback)

        # Create new strip. Start frame is mandatory but int only, so round it up to avoid clashing with previous one because of rouding error
        strip = b.current_track.strips.new(name, int(start + 1), b.current_mapping_action)
        strip.frame_start = start  # Set start frame again as float (ctor takes only int)
        strip.scale = scale
        # if b.ctx.scene.show_subframe:
        strip.frame_end = end
        strip.action_frame_end
        self.strips_added += 1

        strip.name = name
        strip.blend_type = b.strip_placement_props.blend_type
        strip.extrapolation = b.strip_placement_props.extrapolation
        strip.use_sync_length = b.strip_placement_props.use_sync_length
        strip.use_auto_blend = bool(b.strip_placement_props.blend_mode == "AUTOBLEND")
        strip.blend_in = b.strip_placement_props.blend_in
        strip.blend_out = b.strip_placement_props.blend_out

    def bake_cue_on(self, obj: Object) -> None:
        b = self.bctx

        track = b.current_track
        if not track:
            if b.cue_index <= 0:  # Only log the error 1x
                b.rlog.warning(f"{obj and obj.name} has no NLA track selected. Ignoring", self.bctx.current_traceback)
            return
        self.to_strip()

    def bake_cue(self) -> None:
        for obj in self.bctx.object_iter():
            assert self.bctx.current_cue_item, "No cue selected"
            self.bctx.next_track()  # Alternate tracks for each cue change of the current object
            # print(self.bctx.cue_index)
            if log.isEnabledFor(logging.TRACE):  # type: ignore
                log.trace(f"Baking on object {obj} ")  # type: ignore
            self.bake_cue_on(obj)

    def execute(self, ctx: Context) -> set[str]:
        self.bctx = baking_utils.BakingContext(ctx)
        self.strips_added = 0
        b = self.bctx
        if self.trim_cue_excess:
            trimmed = b.trim_long_cues()
            if trimmed > 0:
                log.info(f"Trimmed {trimmed} Cues as they were too long.")

        wm = ctx.window_manager
        l = len(b.mouth_cue_items)
        log.info(f"About to bake {l} cues")
        wm.progress_begin(0, l)
        try:
            for i, cue_item in enumerate(b.cue_iter()):
                # print(b.cue_index)
                wm.progress_update(i)
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Baking cue {cue_item.cue} ({i}/{l}) ")
                self.bctx.next_track()  # Swap tracks on each cue
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
        l.alert = True
        l.label(text=text, icon="ERROR")

    def draw_info(self) -> None:
        b = self.bctx

        # Redundant validations to allow collapsing this sub-panel while still indicating any errors
        selected_objects = list(b.mprefs.object_selection(b.ctx))

        errors = not b.cprops or not b.mouth_cue_items or not selected_objects or not b.objects
        if not ui_utils.draw_expandable_header(b.prefs, "bake_info_panel_expanded", "Info", self.layout, errors):
            return

        box = self.layout.box().column(align=True)
        line = box.split()
        if b.cprops:
            line.label(text="Capture")
            line.label(text=f"{b.cprops.sound_file_basename}.{b.cprops.sound_file_extension}")
        else:
            ui_utils.draw_error(self.layout, "No capture selected")

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

    def draw_validation(self) -> None:
        b = self.bctx
        if not b.objects:
            return
        box = None
        for o in b.object_iter():
            errs = b.validate_current_object()

            if errs:
                if not box:
                    box = self.layout.box().column(align=True)
                box.separator()
                row = box.row()
                row.label(text=o.name)

                for e in errs:
                    self.draw_error_inbox(box.row(), e)

    def draw(self, ctx: Context) -> None:
        self.bctx = baking_utils.BakingContext(ctx)
        clp: CueListPreferences = self.bctx.prefs.cue_list_prefs

        layout = self.layout
        row = layout.row(align=False)
        row.prop(self.bctx.cprops, "start_frame")
        if self.bctx.the_last_cue_item:
            row.label(text=f"End frame: {self.bctx.the_last_cue_item.end_frame_str(ctx)}")
        layout.prop(ctx.scene, "show_subframe", text="Use subframes")
        row = layout.row(align=False)
        row.prop(self, "trim_cue_excess", text=f"Trim cues longer than")
        row = row.row()
        if not self.trim_cue_excess:
            row.enabled = False
        row.prop(clp, "highlight_long_cues")
        layout.prop(self.bctx.mprefs, "object_selection_type")
        self.draw_info()
        self.draw_validation()
        layout.operator(RemoveCapturedNlaStrips.bl_idname)
        # ui_utils.draw_prop_with_label(m, "rate", "Rate", layout)
