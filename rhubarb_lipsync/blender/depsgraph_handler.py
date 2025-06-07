import logging
import traceback

import bpy
from bpy.types import Context, Depsgraph, Object, Scene

from . import capture_properties, mapping_properties
from .dropdown_helper import DropdownHelper
from .mapping_properties import NlaTrackRef

log = logging.getLogger(__name__)


class DepsgraphHandler:
    """
    Manages Blender's depsgraph_update_post application handler to trigger
    callbacks when specific objects (with mapping) or the scene updates.
    """

    # Static counter to track pending updates
    pending_count = 0
    MAX_PENDING_UPDATES = 2

    @staticmethod
    def handle_track_change(obj: Object, track_field_index: int) -> bool:
        mp = mapping_properties.MappingProperties.from_object(obj)
        track: NlaTrackRef = mp.nla_track1 if track_field_index == 1 else mp.nla_track2
        if not track:
            return False
        change = track.dropdown_helper.detect_item_changes()
        status, idx = change
        if status == DropdownHelper.ChangeStatus.UNCHANGED:
            return False  # Don't call the operator when not change was detected

        # Avoid stack-overflow
        pending = DepsgraphHandler.pending_count
        if pending >= DepsgraphHandler.MAX_PENDING_UPDATES:
            log.warning(f"NLA track_{track_field_index} ref update skipped for {obj.name}: too many pending updates ({pending})")
            return False

        try:
            DepsgraphHandler.pending_count += 1
            log.debug(f"Object: '{obj.name}' changes: {status.name}@{idx}, {track}_{track_field_index} Synchronization triggerd. ({pending})")
            # bpy.ops.rhubarb.sync_nla_track_refs(object_name=obj.name, change_status=status.name, new_index=idx, track_field_index=track_field_index)

            track.dropdown_helper.sync_from_items(change)
        finally:
            DepsgraphHandler.pending_count -= 1
        return True

    @staticmethod
    def object_with_mapping_updated(ctx: Context, obj: Object, mp: mapping_properties.MappingProperties) -> None:
        if not mp.has_NLA_track_selected:
            return
        changed = DepsgraphHandler.handle_track_change(obj, 1)
        changed = DepsgraphHandler.handle_track_change(obj, 2) or changed
        if not changed and log.isEnabledFor(logging.TRACE):  # type: ignore
            log.trace(f"No changes detected for object: {obj.name}")

    @staticmethod
    def sync_capture(ctx: Context, cp: capture_properties.CaptureProperties) -> int:
        if not cp:
            return 0
        if cp.on_strip_update(ctx):
            return 1
        return 0

    @staticmethod
    def scene_updated(ctx: Context, scene: Scene) -> None:
        if log.isEnabledFor(logging.TRACE):  # type: ignore
            log.trace("Scene updated")
        cprops = capture_properties.CaptureListProperties.from_context(ctx)
        # TODO Active strip selection change doesn't generate any events so the sync happens too late and is confusing
        # cprops.sync_selection_from_active_strip(ctx)
        updated_count = 0
        for cp in cprops.items:
            updated_count += DepsgraphHandler.sync_capture(ctx, cp)
        if updated_count > 0 and log.isEnabledFor(logging.DEBUG):
            log.debug(f"Synced {updated_count} Captures")

    @staticmethod
    def on_depsgraph_update_post(scene: Scene, depsgraph: Depsgraph) -> None:
        try:
            ctx: Context = bpy.context
            if not ctx:
                return

            for update in depsgraph.updates:
                if isinstance(update.id, Object):
                    # Get the actual data object so any changes would persist. https://b3d.interplanety.org/en/objects-referring-in-a-depsgraph_update-handler-feature/
                    obj = bpy.data.objects[update.id.name]
                    mp = mapping_properties.MappingProperties.from_object(obj)
                    if not mp:  # Object but with no mapping
                        continue
                    DepsgraphHandler.object_with_mapping_updated(ctx, obj, mp)
                    continue
                if isinstance(update.id, Scene):
                    DepsgraphHandler.scene_updated(ctx, update.id)
        except Exception as e:
            msg = f"Unexpected error occured in depsgraph update post handler: {e}"
            log.error(msg)
            log.debug(traceback.format_exc())

    @staticmethod
    def register() -> None:
        if DepsgraphHandler.on_depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(DepsgraphHandler.on_depsgraph_update_post)

    @staticmethod
    def unregister() -> None:
        if DepsgraphHandler.on_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(DepsgraphHandler.on_depsgraph_update_post)
