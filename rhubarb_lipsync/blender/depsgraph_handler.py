import logging
import bpy
from bpy.types import Context, Depsgraph, Object, Operator, Scene

from . import mapping_properties, ui_utils
from .dropdown_helper import DropdownHelper
from .mapping_properties import NlaTrackRef

log = logging.getLogger(__name__)


class SyncNlaTrackRefs(Operator):
    """Synchronize NLA track references from scene. Has to be done in an operator since changing directly in the call back doesn't persist."""

    bl_idname = "rhubarb.sync_nla_track_refs"
    bl_label = "Sync NLA Track References"
    bl_options = {'INTERNAL'}

    object_name: bpy.props.StringProperty()  # type: ignore
    change_status: bpy.props.StringProperty(default="UNCHANGED")  # type: ignore
    new_index: bpy.props.IntProperty(default=-1)  # type: ignore

    def execute(self, context: Context) -> set[str]:
        obj = bpy.data.objects.get(self.object_name)
        if not obj:
            return {'CANCELLED'}

        mp = mapping_properties.MappingProperties.from_object(obj)
        if not mp or not mp.has_NLA_track_selected:
            return {'CANCELLED'}

        status = DropdownHelper.ChangeStatus[self.change_status]
        change = (status, self.new_index)
        mp.sync_NLA_track_refs_from_scene(change)
        ui_utils.redraw_3dviews(context)
        return {'FINISHED'}


class DepsgraphHandler:
    """
    Manages Blender's depsgraph_update_post application handler to trigger
    callbacks when specific objects (with mapping) or the scene updates.
    """

    @staticmethod
    def handle_track_change(obj: Object, track: NlaTrackRef) -> None:
        status, idx = track.dropdown_helper.detect_item_changes()
        if status == DropdownHelper.ChangeStatus.UNCHANGED:
            return  # Don't call the operator when not change was detected

        bpy.ops.rhubarb.sync_nla_track_refs(object_name=obj.name, change_status=status.name, new_index=idx)
        log.debug(f"Object with mapping updated: {obj.name} changes: {status.name}, New index: {idx}")
        return True

    @staticmethod
    def object_with_mapping_updated(ctx: Context, obj: Object, mp: mapping_properties.MappingProperties) -> None:
        if not mp.has_NLA_track_selected:
            return
        DepsgraphHandler.handle_track_change(obj, mp.nla_track1)
        DepsgraphHandler.handle_track_change(obj, mp.nla_track2)

        if log.isEnabledFor(logging.TRACE):  # type: ignore
            log.trace(f"Object with mapping checked: {obj.name} - No changes detected")

    @staticmethod
    def scene_updated(ctx: Context, scene: Scene) -> None:
        print(f"Scene updated: {scene.name}")

    @staticmethod
    def on_depsgraph_update_post(scene: Scene, depsgraph: Depsgraph) -> None:
        ctx: Context = bpy.context
        if not ctx:
            return

        for update in depsgraph.updates:
            if isinstance(update.id, Object):
                obj: Object = update.id
                mp = mapping_properties.MappingProperties.from_object(obj)
                if not mp:  # Object but with no mapping
                    continue
                DepsgraphHandler.object_with_mapping_updated(ctx, obj, mp)
                continue
            if isinstance(update.id, Scene):
                DepsgraphHandler.scene_updated(ctx, update.id)

    @staticmethod
    def register() -> None:
        if DepsgraphHandler.on_depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(DepsgraphHandler.on_depsgraph_update_post)

    @staticmethod
    def unregister() -> None:
        if DepsgraphHandler.on_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(DepsgraphHandler.on_depsgraph_update_post)
