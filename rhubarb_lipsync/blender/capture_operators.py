import logging

import bpy
from bpy.types import Context

import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, MouthCueList
from rhubarb_lipsync.blender.mapping_properties import MappingProperties

log = logging.getLogger(__name__)


class CreateCaptureProps(bpy.types.Operator):
    """Create new CaptureProperties item and add it to the capture list in the current scene"""

    bl_idname = "rhubarb.create_capture_props"
    bl_label = "Create new capture"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context: Context) -> set[str]:
        rootProps = CaptureListProperties.from_context(context)
        assert rootProps, "Failed to got root properties from the scene. Registration error?"
        log.trace("Creating new capture properties")  # type: ignore
        rootProps.items.add()
        rootProps.index = len(rootProps.items) - 1  # Select the newly created item
        rootProps.dropdown_helper(context).index2name()

        return {'FINISHED'}


class DeleteCaptureProps(bpy.types.Operator):
    """Delete existing CaptureProperties item"""

    bl_idname = "rhubarb.delete_capture_props"
    bl_label = "Delete capture"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        rootProps = CaptureListProperties.from_context(context)
        if not rootProps.selected_item:
            return "No capture selected"
        # TODO Check capture is not runnig
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def execute(self, context: Context) -> set[str]:
        rootProps = CaptureListProperties.from_context(context)
        rootProps.items.remove(rootProps.index)
        rootProps.index = rootProps.index - 1
        rootProps.dropdown_helper(context).index2name()
        return {'FINISHED'}


class ClearCueList(bpy.types.Operator):
    """Removes all captured cues from the cue list"""

    bl_idname = "rhubarb.clear_cue_list"
    bl_label = "Clear the cue list"
    bl_options = {'UNDO'}

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        props = CaptureListProperties.capture_from_context(context)
        if not props:
            return "No capture selected"
        cl: MouthCueList = props.cue_list
        if len(cl.items) <= 0:
            return "Cue list is empty"
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    # def invoke(self, context: Context, event) -> set[int] | set[str]:
    #    wm = context.window_manager
    #    return wm.invoke_confirm(self, event)

    def execute(self, context: Context) -> set[str]:
        props = CaptureListProperties.capture_from_context(context)
        cl: MouthCueList = props.cue_list
        cl.items.clear()

        return {'FINISHED'}
