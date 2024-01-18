import logging

import bpy
from bpy.props import StringProperty, IntProperty
from bpy.types import Context
from typing import Optional

from rhubarb_lipsync.blender.mapping_properties import MappingProperties, NlaTrackRef, MappingItem
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthShapeInfos, MouthShapeInfo
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.ui_utils import IconsManager
import rhubarb_lipsync.blender.mapping_utils as mapping_utils
from bpy.props import EnumProperty

log = logging.getLogger(__name__)


def filtered_actions_enum(prop_group: 'ListFilteredActions', ctx: Context) -> list[tuple[str, str, str, str, int]]:
    try:
        o: bpy.types.Object = ctx.object
        mprops = MappingProperties.from_object(o)

        def action2ico(a: bpy.types.Action):
            if a.asset_data:
                return "ASSET_MANAGER"
            if mapping_utils.is_action_shape_key_action(a):
                return "SHAPEKEY_DATA"
            if not mapping_utils.does_action_fit_object(o, a):
                return "ERROR"
            return "OBJECT_DATAMODE"

        def fields(i, a: bpy.types.Action) -> tuple[str, str, str, str, int]:
            return (a.name, a.name, a.name_full, action2ico(a), i)
            # return (a.name, a.name, a.name_full)

        return [fields(i, a) for i, a in enumerate(mapping_utils.filtered_actions(o, mprops))]
    except Exception as e:
        log.exception(f"Failed to list actions. {e}")
        return [('error', f"FAILED: {e}", 'error', 'CANCEL', 1)]


class ListFilteredActions(bpy.types.Operator):
    bl_idname = "rhubarb.list_filtered_actions"
    bl_label = "Select target Action"
    bl_property = "action_name"
    bl_options = {'UNDO', 'REGISTER'}

    action_name: EnumProperty(name="Action", items=filtered_actions_enum)  # type: ignore
    target_cue_index: IntProperty(name="index", description="Mouth cue index to map the Action for")  # type: ignore

    def mapping_item(self, mprops: MappingProperties) -> Optional[MappingItem]:
        """Maping item based on the target_cue_index"""
        if not mprops:
            return None
        if self.target_cue_index < 0 or self.target_cue_index >= len(mprops.items):
            return None
        return mprops.items[self.target_cue_index]

    @property
    def action(self) -> Optional[bpy.types.Action]:
        return bpy.data.actions.get(self.action_str)

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    @classmethod
    def description(csl, context: Context, self: 'ListFilteredActions') -> str:
        mprops: MappingProperties = MappingProperties.from_context(context)

        # mi = self.mapping_item(mprops) # 'self' is dummy, only have properties
        mi = ListFilteredActions.mapping_item(self, mprops)

        if mi is None:
            return "Invalid target cue index selected"
        if not mi.action:
            return f"'Cue: {mi.key}'"
        return f"Action: {mi.action_str}\nRange: {mi.frame_range_str} \nCue: {mi.key}"

    def invoke(self, context: Context, event: bpy.types.Event) -> set[str]:
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mi = self.mapping_item(mprops)
        if not mi:
            self.report(type={"ERROR"}, message="Invalid target cue index selected.")
            return {'CANCELLED'}
        mi.action = self.action
        ui_utils.redraw_3dviews(context)

        return {'FINISHED'}


class SetActionFrameRange(bpy.types.Operator):
    bl_idname = "rhubarb.set_action_framerange"
    bl_label = "Set action framerange"
    bl_options = {'UNDO', 'REGISTER'}

    target_cue_index: IntProperty(name="index", description="Mouth cue index to set the frame range for")  # type: ignore

    def mapping_item(self, mprops: MappingProperties) -> Optional[MappingItem]:
        """Maping item based on the target_cue_index"""
        if not mprops:
            return None
        if self.target_cue_index < 0 or self.target_cue_index >= len(mprops.items):
            return None
        return mprops.items[self.target_cue_index]

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    @classmethod
    def description(csl, context: Context, self: 'ListFilteredActions') -> str:
        mprops: MappingProperties = MappingProperties.from_context(context)

        # mi = self.mapping_item(mprops) # 'self' is dummy, only have properties
        mi = SetActionFrameRange.mapping_item(self, mprops)

        if mi is None:
            return "Invalid target cue index selected"
        return f"Set frame range of the Action for this mapping\nRange: {mi.frame_range_str}"

    def draw(self, context: Context) -> None:
        mprops: MappingProperties = MappingProperties.from_context(context)
        layout = self.layout

        layout.separator()
        layout.label(text=f"{mprops.index}")

    def invoke(self, context: Context, event: bpy.types.Event) -> set[str]:
        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mi = self.mapping_item(mprops)
        if not mi:
            self.report(type={"ERROR"}, message="Invalid target cue index selected.")
            return {'CANCELLED'}

        ui_utils.redraw_3dviews(context)

        return {'FINISHED'}


class ClearMappedActions(bpy.types.Operator):
    """Remove the mapped action for this cue index"""

    bl_idname = "rhubarb.clear_mapped_action"
    bl_label = "Clear the mapped action"
    bl_options = {'UNDO', 'REGISTER'}

    target_cue_index: IntProperty(name="index", description="Mouth cue index to remote the Action from")  # type: ignore

    def mapping_item(self, mprops: MappingProperties) -> Optional[MappingItem]:
        """Maping item based on the target_cue_index"""
        if not mprops:
            return None
        if self.target_cue_index < 0 or self.target_cue_index >= len(mprops.items):
            return None
        return mprops.items[self.target_cue_index]

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mi = ListFilteredActions.mapping_item(self, mprops)
        mi = self.mapping_item(mprops)
        if not mi:
            self.report(type={"INFO"}, message="There is no Action mapped")
            return {'CANCELLED'}
        mi.action = None
        ui_utils.redraw_3dviews(context)

        return {'FINISHED'}


class BuildCueInfoUIList(bpy.types.Operator):
    """Populate the cue mapping list on the active object with the know cue types."""

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
        mprops.build_items(context.active_object)

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
                self.report(type={"ERROR"}, message="No cue key provided and no mapping item selected.")
                return {'CANCELLED'}
            self.key = si.key

        draw = lambda this, ctx: ShowCueInfoHelp.draw_popup(this, self.key, ctx)
        msi: MouthShapeInfo = MouthShapeInfos[self.key].value
        title = f"{msi.key_displ}  {msi.short_dest}"
        bpy.context.window_manager.popup_menu(draw, title=f"{title:<25}", icon="INFO")

        return {'FINISHED'}


class CreateNLATrack(bpy.types.Operator):
    """Create a new NLA track to bake the actions into."""

    name: StringProperty("Name", description="Name of the track to create")  # type:ignore
    track_field_name: StringProperty(name="Track", description="Name of the NltTrackRef attr on the MappingProperties (internal)")  # type:ignore

    bl_idname = "rhubarb.new_nla_track"
    bl_label = "New NLA track"

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    def execute(self, ctx: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(ctx)
        o = ctx.object

        if mapping_utils.does_object_support_shapekey_actions(o):
            ad = o.data.shape_keys.animation_data
            if not ad:  # No shapke-key animation data, create them first
                o.data.shape_keys.animation_data_create()
                ad = o.data.shape_keys.animation_data
                assert ad, "Failed to create shape-keys animation data"
        else:
            ad = o.animation_data
            if not ad:  # No animation data, create them first
                o.animation_data_create()
                ad = o.animation_data
                assert ad, "Failed to create object animation data"
        tracks = ad.nla_tracks
        t = tracks.new()
        t.name = self.name
        msg = f"Created new NLA track: {self.name}. Shapekey track: {mapping_utils.does_object_support_shapekey_actions(o)}"
        log.debug(msg)
        self.report({"INFO"}, msg)
        if self.track_field_name:  # Select the newly created track
            trackRef: NlaTrackRef = getattr(mprops, self.track_field_name)
            trackRef.object = o
            trackRef.dropdown_helper.select_last()

        return {'FINISHED'}
