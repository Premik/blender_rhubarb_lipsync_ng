import logging
from functools import cached_property
from types import ModuleType
from typing import Dict, List, Optional, cast
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty, BoolProperty
from bpy.types import Context, Object, UILayout, NlaTrack
from typing import Any, Callable, Optional, cast, Generator, Iterator

from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, MouthCueList, MouthCueListItem
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, MappingItem, NlaTrackRef
from rhubarb_lipsync.blender.preferences import CueListPreferences, RhubarbAddonPreferences, MappingPreferences
from rhubarb_lipsync.rhubarb.log_manager import logManager
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfos, MouthShapeInfo
import rhubarb_lipsync.blender.ui_utils as ui_utils
import traceback
from rhubarb_lipsync.blender.ui_utils import IconsManager

log = logging.getLogger(__name__)


def objects_with_mapping(objects: Iterator[Object]) -> Generator[Object | Any, Any, None]:
    """Filter all objects which non-blank mapping properties"""
    for o in objects or []:
        mp = MappingProperties.from_object(o)
        if mp and mp.has_any_mapping:
            yield o


def objects_to_bake(ctx: Context) -> Generator[Object | Any, Any, None]:
    prefs = RhubarbAddonPreferences.from_context(ctx)
    mp: MappingPreferences = prefs.mapping_prefs
    yield from objects_with_mapping(mp.object_selection(ctx))


def object_validation(obj: Object, ctx: Context) -> list[str]:
    mprops: MappingProperties = MappingProperties.from_object(obj)
    prefs = RhubarbAddonPreferences.from_context(ctx)

    if not mprops:
        return ["Object has no mapping properties"]
    if not mprops.has_any_mapping:
        return ["Object has no mapping"]
    ret: list[str] = []
    extended: list[str] = []
    if prefs.use_extended_shapes:
        extended = [msi.key for msi in MouthShapeInfos.extended()]
    if mprops.nla_map_action:  # Find unmapped cues (regular action). Ignore extended if not used
        lst = ','.join([k for k in mprops.blank_keys if k not in extended])
        ret += [f"{lst} has no action mapped"]

    if mprops.nla_map_shapekey:
        lst = ','.join([k for k in mprops.blank_shapekeys if k not in extended])
        ret += [f"{lst} has no shape-action mapped"]

    track: NlaTrackRef = mprops.nla_track1
    if not track.selected_item(ctx):
        ret += [f"no NLA track selected"]
    return ret


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

    def cue_list(self, ctx: Context) -> Optional[MouthCueList]:
        cprops = CaptureListProperties.capture_from_context(ctx)
        if not cprops:
            return None
        return cprops.cue_list

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def invoke(self, context: Context, event: bpy.types.Event) -> set[int] | set[str]:
        # Open dialog
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=340)

    def execute(self, ctx: Context) -> set[str]:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        mp: MappingPreferences = prefs.mapping_prefs
        cprops = CaptureListProperties.capture_from_context(ctx)
        mprops: MappingProperties = MappingProperties.from_context(ctx)
        trackRef: NlaTrackRef = mprops.nla_track1
        track: NlaTrack = trackRef.selected_item
        # track.strips

        cueList: MouthCueList = cprops.cue_list
        for cue in cueList.items:
            c: MouthCueListItem = cue

        return {'FINISHED'}

    def draw_error_inbox(self, l: UILayout, text: str) -> None:
        l.alert = True
        l.label(text=text, icon="ERROR")

    def draw_info(self, ctx: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        mp: MappingPreferences = prefs.mapping_prefs
        cprops = CaptureListProperties.capture_from_context(ctx)

        if not cprops:
            ui_utils.draw_error(self.layout, "No capture selected")
            return

        box = self.layout.box().column(align=True)

        line = box.split()
        line.label(text="Capture")
        line.label(text=f"{cprops.sound_file_basename}.{cprops.sound_file_extension}")

        line = box.split()
        line.label(text="Mouth cues")
        cl = self.cue_list(ctx)
        if cl and cl.items:
            line.label(text=str(len(cl.items)))
        else:
            self.draw_error_inbox(line, "No cues")

        line = box.split()
        line.label(text="Objects selected")
        selected_objects = list(mp.object_selection(ctx))
        if selected_objects:
            line.label(text=f"{len(selected_objects)}")
        else:
            self.draw_error_inbox(line, "None")

        objs_to_bake = list(objects_to_bake(ctx))
        line = box.split()
        line.label(text="Objects with mapping")
        if len(objs_to_bake):
            line.label(text=f"{len(objs_to_bake)}")
        else:
            self.draw_error_inbox(line, "None of the selected")
        box = self.layout.box().column(align=True)
        for o in objects_to_bake(ctx):
            errs = object_validation(o, ctx)
            if errs:
                box.separator()
                row = box.row()
                row.label(text=o.name)

                for e in errs:
                    self.draw_error_inbox(box.row(), e)

    def draw(self, ctx: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        mlp: MappingPreferences = prefs.mapping_prefs
        cprops = CaptureListProperties.capture_from_context(ctx)
        cl = self.cue_list(ctx)

        layout = self.layout
        row = layout.row(align=False)
        row.prop(cprops, "start_frame")
        if cl and cl.last_item:
            row.label(text=f"End frame: {cl.last_item.end_frame_str(ctx)}")
        layout.prop(mlp, "object_selection_type")
        self.draw_info(ctx)
        # ui_utils.draw_prop_with_label(m, "rate", "Rate", layout)
