import logging

import bpy
from bpy.types import Context, Depsgraph, Object, Operator, Scene

from . import mapping_properties
from .dropdown_helper import DropdownHelper
from .mapping_properties import NlaTrackRef

log = logging.getLogger(__name__)


class DummyOp(Operator):
    bl_idname = "rhubarb.dummy_op"
    bl_label = "Helper for unit tests"
    bl_options = {'INTERNAL'}

    def execute(self, context: Context) -> set[str]:
        log.warn("\n---------------------\nDummy op\n--------------------\n\n")
        return {'FINISHED'}


class DepsgraphHandler:
    """
    Manages Blender's depsgraph_update_post application handler to trigger
    callbacks when specific objects (with mapping) or the scene updates.
    """

    # Static counter to track pending updates
    pending_count = 0
    MAX_PENDING_UPDATES = 2

    @staticmethod
    def handle_track_change(obj: Object, track: NlaTrackRef, track_field_index: int) -> None:
        status, idx = track.dropdown_helper.detect_item_changes()
        if status == DropdownHelper.ChangeStatus.UNCHANGED:
            return  # Don't call the operator when not change was detected

        # Avoid stack-overflow
        pending = DepsgraphHandler.pending_count
        if pending >= DepsgraphHandler.MAX_PENDING_UPDATES:
            log.warning(f"NLA track_{track_field_index} ref update skipped for {obj.name}: too many pending updates ({pending})")
            return False

        try:
            DepsgraphHandler.pending_count += 1
            log.debug(f"Object with mapping updated: {obj.name} changes: {status.name}, {track}_{track_field_index} Synchronization triggerd. ({pending})")
            bpy.ops.rhubarb.sync_nla_track_refs(object_name=obj.name, change_status=status.name, new_index=idx, track_field_index=track_field_index)
        finally:
            DepsgraphHandler.pending_count -= 1
        return True

    @staticmethod
    def object_with_mapping_updated(ctx: Context, obj: Object, mp: mapping_properties.MappingProperties) -> None:
        if not mp.has_NLA_track_selected:
            return
        changed = False
        changed = changed or DepsgraphHandler.handle_track_change(obj, mp.nla_track1, 1)
        changed = changed or DepsgraphHandler.handle_track_change(obj, mp.nla_track2, 2)
        if log.isEnabledFor(logging.TRACE):  # type: ignore
            log.trace(f"No changes detected for object: {obj.name}")

    @staticmethod
    def scene_updated(ctx: Context, scene: Scene) -> None:
        if log.isEnabledFor(logging.TRACE):  # type: ignore
            log.trace("Scene updated")

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
