import bpy
from bpy.types import Context, Depsgraph, Object, Operator, Scene

from . import mapping_properties, ui_utils


class SyncNlaTrackRefs(Operator):
    """Synchronize NLA track references from scene"""

    bl_idname = "rhubarb.sync_nla_track_refs"
    bl_label = "Sync NLA Track References"
    bl_options = {'INTERNAL'}

    object_name: bpy.props.StringProperty()

    def execute(self, context: Context) -> set[str]:
        obj = bpy.data.objects.get(self.object_name)
        if not obj:
            return {'CANCELLED'}

        mp = mapping_properties.MappingProperties.from_object(obj)
        if not mp or not mp.has_NLA_track_selected:
            return {'CANCELLED'}

        mp.sync_NLA_track_refs_from_scene()
        ui_utils.redraw_3dviews(context)
        return {'FINISHED'}


class DepsgraphHandler:
    """
    Manages Blender's depsgraph_update_post application handler to trigger
    callbacks when specific objects (with mapping) or the scene updates.
    """

    @staticmethod
    def object_with_mapping_updated(ctx: Context, obj: Object, mp: mapping_properties.MappingProperties) -> None:
        if not mp.has_NLA_track_selected:
            return
        # mp.sync_NLA_track_refs_from_scene()
        bpy.ops.rhubarb.sync_nla_track_refs(object_name=obj.name)

        print(f"Object with mapping updated: {obj.name}")

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
