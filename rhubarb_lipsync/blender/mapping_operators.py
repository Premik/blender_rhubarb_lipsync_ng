import logging
from itertools import islice
from typing import Iterator, Optional

import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Context, Object

from .. import IconsManager
from ..rhubarb.mouth_shape_info import MouthShapeInfo, MouthShapeInfos
from . import mapping_utils, ui_utils
from .mapping_properties import MappingItem, MappingProperties, NlaTrackRef
from .preferences import MappingPreferences, RhubarbAddonPreferences

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


def objects_with_mapping_filtered(context: Context) -> Iterator[Object]:
    prefs = RhubarbAddonPreferences.from_context(context)
    mlp: MappingPreferences = prefs.mapping_prefs
    obj_sel = mlp.object_selection_filtered(context)
    return mapping_utils.objects_with_mapping(obj_sel)


class ListFilteredActions(bpy.types.Operator):
    bl_idname = "rhubarb.list_filtered_actions"
    bl_label = "Select target Action"
    bl_property = "action_name"
    bl_options = {'UNDO'}

    action_name: EnumProperty(name="Action", items=filtered_actions_enum)  # type: ignore
    target_cue_index: IntProperty(name="index", description="Mouth cue index to map the Action for")  # type: ignore

    @property
    def action(self) -> Optional[bpy.types.Action]:
        return bpy.data.actions.get(self.action_name)

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    @classmethod
    def description(csl, context: Context, self: 'ListFilteredActions') -> str:
        mprops: MappingProperties = MappingProperties.from_context(context)

        mi = mprops[self.target_cue_index]

        if mi is None:
            return "Invalid target cue index selected"
        if not mi.action:
            return f"'Cue: {mi.key}'"
        return f"Action: {mi.action_str}\nRange: {mi.frame_range_str} \nCue: {mi.key}"

    def invoke(self, context: Context, event: bpy.types.Event) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mprops.index = self.target_cue_index
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mi = mprops[self.target_cue_index]
        if not mi:
            self.report(type={"ERROR"}, message="Invalid target cue index selected.")
            return {'CANCELLED'}
        mi.action = self.action
        ui_utils.redraw_3dviews(context)

        return {'FINISHED'}


class SetActionFrameRange(bpy.types.Operator):
    bl_idname = "rhubarb.set_action_framerange"
    bl_label = "Set start/end frames of the Action"
    bl_options = {'UNDO'}

    target_cue_index: IntProperty(name="index", description="Mouth cue index to set the frame range for")  # type: ignore

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    @classmethod
    def description(csl, context: Context, self: 'ListFilteredActions') -> str:
        mprops: MappingProperties = MappingProperties.from_context(context)

        mi = mprops[self.target_cue_index]

        if mi is None:
            return "Invalid target cue index selected"
        if mi.custom_frame_ranage:
            range_str = "Custom range"
        else:
            range_str = "Default range"
        return f"Set frame range of the Action for this mapping\n{range_str}: {mi.frame_range_str}"

    def draw(self, context: Context) -> None:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mi = mprops[self.target_cue_index]
        box = self.layout.box()
        box.label(text=f"Range: {mi.frame_range_str}")
        self.layout.prop(mi, "custom_frame_ranage")
        row = self.layout.row(align=True)
        row.enabled = mi.custom_frame_ranage
        row.prop(mi, "frame_start", text="Start")
        row.prop(mi, "frame_count", text="Count")
        row = self.layout.row(align=True)
        row.enabled = mi.custom_frame_ranage

        def shift_op(sign: str, delta: float, icon: str):
            blid = SetShiftActionFrameRangeStart.bl_idname
            op: SetShiftActionFrameRangeStart = row.operator(blid, text=f"{sign}{mi.frame_count:.2f}", icon=icon)
            op.delta = delta
            op.target_cue_index = self.target_cue_index

        shift_op("-", -mi.frame_count, icon="PLAY_REVERSE")
        shift_op("+", +mi.frame_count, icon="PLAY")

        # row.prop(mi.frame_end, "End")

    def invoke(self, context: Context, event: bpy.types.Event) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mprops.index = self.target_cue_index
        return context.window_manager.invoke_props_dialog(self, width=300)

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mi = mprops[self.target_cue_index]
        if not mi:
            self.report(type={"ERROR"}, message="Invalid target cue index selected.")
            return {'CANCELLED'}

        ui_utils.redraw_3dviews(context)

        return {'FINISHED'}


class SetShiftActionFrameRangeStart(bpy.types.Operator):
    bl_idname = "rhubarb.shift_action_framerange_start"
    bl_label = "Offset start by"
    bl_options = {'UNDO'}

    target_cue_index: IntProperty(name="index", description="Mouth cue index to set the frame range for")  # type: ignore
    delta: FloatProperty(name="delta", description="How many frames to shift the start frame by")  # type: ignore

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    @classmethod
    def description(csl, context: Context, self: 'ListFilteredActions') -> str:
        return f"Shift the start frame of the custom subrange by {self.delta} frames"

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mi = mprops[self.target_cue_index]
        if not mi:
            self.report(type={"ERROR"}, message="Invalid target cue index selected.")
            return {'CANCELLED'}
        mi.frame_start += self.delta

        return {'FINISHED'}


class ClearMappedActions(bpy.types.Operator):
    """Remove the mapped Action for this Cue type"""

    bl_idname = "rhubarb.clear_mapped_action"
    bl_label = "Clear the mapped action"
    bl_options = {'UNDO'}

    target_cue_index: IntProperty(name="index", description="Mouth cue index to remove the Action from")  # type: ignore

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context, MappingProperties.context_selection_validation)

    def execute(self, context: Context) -> set[str]:
        mprops: MappingProperties = MappingProperties.from_context(context)
        mi = mprops[self.target_cue_index]
        mprops.index = self.target_cue_index
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
        row.template_icon(icon_value=IconsManager.cue_icon(key), scale=6)
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
        mprops.index = MouthShapeInfos.key2index(self.key)
        draw = lambda this, ctx: ShowCueInfoHelp.draw_popup(this, self.key, ctx)
        msi: MouthShapeInfo = MouthShapeInfos[self.key].value
        title = f"{msi.key_displ}  {msi.short_dest}"
        context.window_manager.popup_menu(draw, title=f"{title:<25}", icon="INFO")

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


class PreviewMappingAction(bpy.types.Operator):
    """Preview the Action(s) mapped for this Cue type"""

    bl_idname = "rhubarb.preview_mapping_action"
    bl_label = "Preview"

    target_cue_index: IntProperty(name="index", description="Mouth cue index to preview", default=-1)  # type: ignore

    @classmethod
    def disabled_reason(cls, context: Context, limit=100) -> str:
        if not context.scene:
            return "No active scene"
        objs = list(islice(objects_with_mapping_filtered(context), limit if limit else None))
        if not objs:
            return "No object with (non-empty) mapping selected"
        for o in objs:
            if mapping_utils.does_object_support_shapekey_actions(o):
                ad = o.data.shape_keys.animation_data
            else:
                ad = o.animation_data

            if not ad:
                return f"The object '{o.name}' has no animation data."
            if ad.is_property_readonly("action"):
                return f"The 'action' attribute of the object '{o.name}' animation data is readonly. Are you tweaking a NLA strip?"
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def execute(self, context: Context) -> set[str]:
        # prefs = RhubarbAddonPreferences.from_context(context)
        # mlp: MappingPreferences = prefs.mapping_prefs

        error = PreviewMappingAction.disabled_reason(context, 0)
        if error:
            self.report({"ERROR"}, error)
            return {'CANCELLED'}

        cue_index: int = self.target_cue_index
        active_mi: MappingItem = MappingItem.from_object(context.object, cue_index)

        # Play or Stop depends on the selected active Object
        is_active_active = mapping_utils.is_mapping_item_active(context, active_mi, context.object)
        for o in objects_with_mapping_filtered(context):
            mi: MappingItem = MappingItem.from_object(o, cue_index)
            if not mi:
                self.report(type={"ERROR"}, message=f"Invalid target cue index {cue_index}. Object has not mapping item.")
                return {'CANCELLED'}

            if is_active_active:  # Active object has the Mapping Item Active, stop all previews
                mapping_utils.deactivate_mapping_item(context, o)
            else:
                mapping_utils.activate_mapping_item(context, mi, o)

        frame_count = active_mi.frame_range[1] - active_mi.frame_range[0]
        if frame_count > 1 and not is_active_active:
            # Shoud play has more than a single frame=> trigger playback for the subrange
            bpy.ops.rhubarb.play_range(play_frames=int(frame_count), start_frame=int(active_mi.frame_range[0]))

        return {'FINISHED'}
