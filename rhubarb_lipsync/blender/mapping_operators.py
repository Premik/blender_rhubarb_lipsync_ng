import logging

import bpy
from bpy.props import StringProperty
from bpy.types import Context

from rhubarb_lipsync.blender.mapping_properties import MappingProperties, NlaTrackRef
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthShapeInfos, MouthShapeInfo
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.ui_utils import IconsManager

log = logging.getLogger(__name__)


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
                self.report(type={'ERROR'}, message="No cue key provided and no mapping item selected.")
                return {'CANCELLED'}
            self.key = si.key

        draw = lambda this, ctx: ShowCueInfoHelp.draw_popup(this, self.key, ctx)
        msi: MouthShapeInfo = MouthShapeInfos[self.key].value
        title = f"{msi.key_displ}  {msi.short_dest}"
        bpy.context.window_manager.popup_menu(draw, title=f"{title:<25}", icon='INFO')

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
        if self.track_field_name:  # Select the newly created track
            trackRef: NlaTrackRef = getattr(mprops, self.track_field_name)
            trackRef.object = ctx.object
            trackRef.dropdown_helper.select_last()

        return {'FINISHED'}
