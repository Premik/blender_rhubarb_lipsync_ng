import logging
from functools import cached_property
from pydoc import describe
from types import ModuleType
from typing import Dict, List, Optional, cast
import math
import re
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, Object, UILayout, NlaTrack, NlaStrip
from typing import Any, Callable, Generator, Iterator

from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, ResultLogListProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, MappingItem, NlaTrackRef, StripPlacementProperties
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences, MappingPreferences
from rhubarb_lipsync.rhubarb.log_manager import logManager
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfos, MouthShapeInfo
import rhubarb_lipsync.blender.ui_utils as ui_utils
import rhubarb_lipsync.blender.baking_utils as baking_utils
from rhubarb_lipsync.blender.ui_utils import IconsManager

log = logging.getLogger(__name__)


class RemoveCapturedNlaStrips(bpy.types.Operator):
    """Remove NLA Strips on bake-selected NLA Tracks on a given frame range. Making room for another bake."""

    bl_idname = "rhubarb.remove_captured_nla_strips"
    bl_label = "Remove strips"
    bl_options = {'UNDO', 'REGISTER'}

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
            self.report({'ERROR'}, f"No matching object in selection")
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
    bl_options = {'UNDO', 'REGISTER'}

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
    bl_options = {'UNDO', 'REGISTER'}

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
    bl_options = {'UNDO', 'REGISTER'}

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


class BakeToNLA(bpy.types.Operator):
    """Bake the selected objects to nla tracks"""

    bl_idname = "rhubarb.bake_to_nla"
    bl_label = "Bake to NLA"

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        error_common = CaptureProperties.sound_selection_validation(context, False)
        if error_common:
            return error_common
        error_common = MappingProperties.context_selection_validation(context)
        if error_common:
            return error_common
        props = CaptureListProperties.capture_from_context(context)
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def invoke(self, context: Context, event: bpy.types.Event) -> set[int] | set[str]:
        # Open dialog

        rll: ResultLogListProperties = CaptureListProperties.from_context(context).last_resut_log
        rll.clear()  # Clear log entries from last bake
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=340)

    def to_strip(self) -> None:
        b = self.bctx
        cue = b.current_cue

        if not b.current_mapping_action:
            b.rlog.warning(f"There is no mapping for the cue {cue and cue.cue} in the capture. Ignoring", self.bctx.current_trace)
            return
        name = f"{cue.cue.info.key_displ}.{str(b.cue_index).zfill(3)}"

        # Shift the start frame
        start = cue.frame_float(b.ctx) + b.strip_placement_props.offset_start
        # Calculate the desired strip length based on cue length and include the offset
        strip_duration = cue.duration_frames_float(b.ctx) + b.strip_placement_props.overlap_length
        # Try to scale the strip to strip_placement the cue duration with the blendings included.
        scale = b.current_mapping_action_scale(strip_duration, b.strip_placement_props.scale_min, b.strip_placement_props.scale_max)

        # Calculate the end frame based on the scale and the start. This is where the action ends after scaling (with offsets)
        # end = start + b.current_mapping_action_length_frames * scale
        # Set the strip end to the cue end (plus offset) no matter where the actual action ends.
        end = cue.end_frame_float(b.ctx) + b.strip_placement_props.offset_end

        # Crop the previous strip-end to make a room for the current strip start (if needed)
        if baking_utils.trim_strip_end_at(b.current_track, start):
            b.rlog.warning("Had to trim previous strip to make room for this one", self.bctx.current_trace)

        # Create new strip. Start frame is mandatory but int only, so round it up to avoid clashing with previous one because of rouding error
        strip = b.current_track.strips.new(name, int(start + 1), b.current_mapping_action)
        strip.frame_start = start  # Set start frame again as float (ctor takes only int)
        strip.scale = scale
        # if b.ctx.scene.show_subframe:
        strip.frame_end = end
        self.strips_added += 1

        strip.name = name
        strip.blend_type = b.strip_placement_props.blend_type
        strip.extrapolation = b.strip_placement_props.extrapolation
        strip.use_sync_length = b.strip_placement_props.use_sync_length
        strip.use_auto_blend = b.strip_placement_props.use_auto_blend
        strip.blend_in = b.strip_placement_props.blend_in
        strip.blend_out = b.strip_placement_props.blend_out

        # strip.frame_end = c.end_frame_float(b.ctx)

    def bake_cue_on(self, object: Object) -> None:
        b = self.bctx

        track = b.current_track
        if not track:
            if b.cue_index <= 0:  # Only log the error 1x
                b.rlog.warning(f"{object and object.name} has no NLA track selected. Ignoring", self.bctx.current_trace)
            return
        self.to_strip()

    def bake_cue(self) -> None:
        for o in self.bctx.object_iter():
            assert self.bctx.current_cue, "No cue selected"
            self.bctx.next_track()  # Alternate tracks for each cue change of the current object
            # print(self.bctx.cue_index)
            if log.isEnabledFor(logging.TRACE):  # type: ignore
                log.trace(f"Baking on object {o} ")  # type: ignore
            self.bake_cue_on(o)

    def execute(self, ctx: Context) -> set[str]:
        self.bctx = baking_utils.BakingContext(ctx)
        self.strips_added = 0
        b = self.bctx
        wm = ctx.window_manager
        l = len(b.cue_items)
        log.info(f"About to bake {l} cues")
        wm.progress_begin(0, l)
        try:
            for i, c in enumerate(b.cue_iter()):
                # print(b.cue_index)
                wm.progress_update(i)
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Baking cue {c.cue} ({i}/{l}) ")
                self.bctx.next_track()  # Swap tracks on each cue
                self.bake_cue()
            msg = f"Baked {l} cues to {self.strips_added} action strips"
            self.bctx.rlog.info(msg, self.bctx.current_trace)
            self.report({'INFO'}, msg)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            log.exception(e)
            self.bctx.rlog.error(str(e), self.bctx.current_trace)
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

        errors = not b.cprops or not b.cue_items or not selected_objects or not b.objects
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
        if b.cue_items:
            line.label(text=str(len(b.cue_items)))
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

        layout = self.layout
        row = layout.row(align=False)
        row.prop(self.bctx.cprops, "start_frame")
        if self.bctx.last_cue:
            row.label(text=f"End frame: {self.bctx.last_cue.end_frame_str(ctx)}")
        layout.prop(ctx.scene, "show_subframe", text="Use subframes")
        layout.prop(self.bctx.mprefs, "object_selection_type")
        self.draw_info()
        self.draw_validation()
        layout.operator(RemoveCapturedNlaStrips.bl_idname)
        # ui_utils.draw_prop_with_label(m, "rate", "Rate", layout)
