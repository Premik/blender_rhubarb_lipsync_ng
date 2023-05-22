import logging
from functools import cached_property
from types import ModuleType
from typing import Dict, List, Optional, cast
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty, BoolProperty
from bpy.types import Context, Object, UILayout
from typing import Any, Callable, Optional, cast, Generator, Iterator

from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, MouthCueList, JobProperties
from rhubarb_lipsync.blender.mapping_properties import MappingProperties, MappingItem
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

    if not mprops.nla_track1:
        ret += [f"no NLA track selected"]
    return ret


class BuildCueInfoUIList(bpy.types.Operator):
    """Populate the cue mapping list with the know cue types."""

    bl_idname = "rhubarb.build_cueinfo_uilist"
    bl_label = "Initialize mapping list"

    # @classmethod
    # def disabled_reason(cls, context: Context, limit=0) -> str:
    #    props = CaptureListProperties.capture_from_context(context)
    #    mporps: MappingList = props.mapping
    #    if len(mporps.items) > 0:
    #        return f"Cue mapping info is already populated"
    #    return ""

    # @classmethod
    # def poll(cls, context: Context) -> bool:
    #    return ui_utils.validation_poll(cls, context)

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mprops.items.clear()
        mprops.build_items()

        return {'FINISHED'}


class ShowCueInfoHelp(bpy.types.Operator):
    """Show a popup with cue type description."""

    bl_idname = "rhubarb.show_cueinfo_help"
    bl_label = "Cue type help"

    key: StringProperty("Key", description="The cue type key to show the help on.", default="")  # type:ignore

    @staticmethod
    def draw_popup(this: bpy.types.UIPopupMenu, key: str, context: Context) -> None:
        layout = this.layout
        msi: MouthShapeInfo = MouthShapeInfos[key].value
        # split = layout.split(factor=0.2)
        row = layout.row()
        row.template_icon(icon_value=IconsManager.cue_image(key), scale=6)
        col = row.column(align=False)
        lines = msi.description.splitlines()
        for l in lines:
            col.label(text=l)

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        if not self.key:
            si = mprops.selected_item
            if not si:
                self.report(type={'ERROR'}, message=f"No cue key provided and no mapping item selected.")
                return {'CANCELLED'}
            self.key = si.key

        draw = lambda this, ctx: ShowCueInfoHelp.draw_popup(this, self.key, ctx)
        msi: MouthShapeInfo = MouthShapeInfos[self.key].value
        bpy.context.window_manager.popup_menu(draw, title=f"{msi.short_dest:<25}", icon='INFO')

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

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)

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


class CreateNLATrack(bpy.types.Operator):
    """Create a new NLA track to bake the actions into."""

    name: StringProperty("Name", description="Name of the track to create")  # type:ignore

    bl_idname = "rhubarb.new_nla_track"
    bl_label = "New NLA track"

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    def execute(self, ctx: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(ctx)
        ad = ctx.object.animation_data
        if not ad:  # No animation data, create them first
            ctx.object.animation_data_create()
            ad = ctx.object.animation_data
            assert ad, "Failed to create new animation data"
        tracks = ad.nla_tracks
        t = tracks.new()
        t.name = self.name
        msg = f"Created new NLA track: {self.name}"
        log.debug(msg)
        self.report({'INFO'}, msg)

        return {'FINISHED'}
