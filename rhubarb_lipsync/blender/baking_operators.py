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

from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, MouthCueList, MouthCueListItem
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, MappingItem, NlaTrackRef
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences, MappingPreferences
from rhubarb_lipsync.rhubarb.log_manager import logManager
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfos, MouthShapeInfo
import rhubarb_lipsync.blender.ui_utils as ui_utils
import rhubarb_lipsync.blender.baking_utils as baking_utils
from rhubarb_lipsync.blender.ui_utils import IconsManager

log = logging.getLogger(__name__)


class RemoveNlaStrips(bpy.types.Operator):
    """Remove NLA Strips on a given NLA Track on a given frame range"""

    bl_idname = "rhubarb.remove_nla_strips"
    bl_label = "Remove strips"
    bl_options = {'UNDO', 'REGISTER'}

    start_frame: IntProperty(name="Start Frame", default=1)  # type: ignore
    end_frame: IntProperty(name="Start Frame", default=1)  # type: ignore
    # track: PointerProperty(type=NlaTrack, name="NLA Track")  # type: ignore
    track_ref: PointerProperty(type=NlaTrackRef, name="Track")  # type: ignore

    # @classmethod
    # def disabled_reason(cls, context: Context, limit=0) -> str:
    #     start: int = self.start_frame
    #     props = CaptureListProperties.capture_from_context(context)
    #     mporps: MappingList = props.mapping
    #     if len(mporps.items) > 0:
    #         return f"Cue mapping info is already populated"
    #     return ""

    # @classmethod
    # def poll(cls, context: Context) -> bool:
    #     return ui_utils.validation_poll(cls, context)

    def execute(self, context: Context) -> set[str]:
        start: int = self.start_frame
        end: int = self.end_frame
        tref: NlaTrackRef = self.track_ref
        if end - start <= 0:
            msg = f"No frames between {start} and {end}."
            self.report({'ERROR'}, msg)
            log.error(msg)
            return {'CANCELLED'}
        track: NlaTrack = tref.selected_item()

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

        CaptureListProperties.from_context(context).last_error = ""
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=340)

    def bake_cue_on(self, object: Object) -> None:
        b = self.bctx

        track = b.current_track
        if not track:
            log.error(f"{object} has no NLA track selected. Ignoring")
            return
        c = b.current_cue
        m = b.current_mapping_item
        if not m or not m.action:
            log.error(f"There is no mapping for the cue {c} in the capture. Ignoring")
            return
        strip = track.strips.new(f"{c.cue}", c.frame(b.ctx), m.action)
        if b.ctx.scene.show_subframe:  # Set start frame again as float (ctor takes only int)
            strip.frame_start = c.frame_float(b.ctx)

        # strip.frame_end = c.end_frame_float(b.ctx)

    def bake_cue(self) -> None:
        for o in self.bctx.object_iter():
            if log.isEnabledFor(logging.TRACE):  # type: ignore
                log.trace(f"Baking on object {o} ")  # type: ignore
            self.bake_cue_on(o)

    def execute(self, ctx: Context) -> set[str]:
        self.bctx = baking_utils.BakingContext(ctx)
        b = self.bctx
        wm = ctx.window_manager
        l = len(b.cue_items)
        log.info(f"About to bake {l} cues")
        wm.progress_begin(0, l)
        try:
            for i, c in enumerate(b.cue_iter()):
                wm.progress_update(i)
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Baking cue {c.cue} ({i}/{l}) ")
                self.bake_cue()
            self.report({'INFO'}, f"Baked {l} cues")
        except Exception as e:
            self.report({'ERROR'}, str(e))
            log.exception(e)

            CaptureListProperties.from_context(ctx).last_error = str(e)
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
        layout.operator(RemoveNlaStrips.bl_idname)
        # ui_utils.draw_prop_with_label(m, "rate", "Rate", layout)
