from lib2to3.fixes.fix_input import context
import logging
from functools import cached_property
from pydoc import describe
from types import ModuleType
from typing import Dict, List, Optional, cast
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty, BoolProperty
from bpy.types import Context, Object, UILayout, NlaTrack, NlaStrip
from typing import Any, Callable, Optional, cast, Generator, Iterator

from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, ResultLogListProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, MappingItem, NlaTrackRef
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
        mitem = b.current_mapping_item

        if not mitem or not mitem.action:
            b.rlog.warning(f"There is no mapping for the cue {cue and cue.cue} in the capture. Ignoring", self.bctx.current_trace)
            return
        name = f"{cue.cue.info.key_displ}.{str(b.cue_index).zfill(3)}"
        start = cue.frame_float(b.ctx) + b.fit_props.blend_start  # Start frame can be shifted
        # The blend start frame changes the length so it won't affect the end frame won't change.
        strip_duration = cue.duration_frames(b.ctx) - b.fit_props.blend_start + b.fit_props.blend_end
        scale = b.fit_props.action_scale(mitem.action, strip_duration)  # Try to scale to fit the cue duration with the blendings included.
        end = cue.end_frame_float(b.ctx) * scale
        strip = b.current_track.strips.new(name, int(start), mitem.action)
        strip.scale = scale
        # if b.ctx.scene.show_subframe:  # Set start frame again as float (ctor takes only int)
        strip.frame_start = start
        strip.frame_end = end
        self.strips_added += 1

        strip.name = name
        strip.blend_type = "COMBINE"
        strip.use_auto_blend = True

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
