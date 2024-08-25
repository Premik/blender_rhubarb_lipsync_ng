import logging

import bpy
from bpy.props import StringProperty
from bpy.types import Context

import rhubarb_lipsync.blender.ui_utils as ui_utils
from .capture_properties import CaptureListProperties, MouthCueList
from ..rhubarb.rhubarb_command import RhubarbParser

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
    """Remove all captured cues from the cue list"""

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

    # def invoke(self, context: Context, event) -> set:
    #    wm = context.window_manager
    #    return wm.invoke_confirm(self, event)

    def execute(self, context: Context) -> set[str]:
        props = CaptureListProperties.capture_from_context(context)
        cl: MouthCueList = props.cue_list
        cl.items.clear()

        return {'FINISHED'}


class ExportCueList2Json(bpy.types.Operator):
    """Export the current cue list of the selected capture to a json file following the rhubarb-cli format"""

    bl_idname = "rhubarb.export_cue_list2json"
    bl_label = "Export to JSON"

    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    filter_glob: StringProperty(default='*.json;', options={'HIDDEN'})  # type: ignore

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        props = CaptureListProperties.capture_from_context(context)
        if not props:
            return "No capture selected"
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def invoke(self, context: Context, event) -> set:
        rootProps = CaptureListProperties.from_context(context)
        if not self.filepath:
            n = rootProps.name
            if not n:
                n = "capture"
            self.filepath = f"{n}.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: Context) -> set[str]:
        cprops = CaptureListProperties.capture_from_context(context)
        cl: MouthCueList = cprops.cue_list
        cues = [c.cue for c in cl.items]
        json = RhubarbParser.unparse_mouth_cues(cues, f"{cprops.sound_file_basename}.{cprops.sound_file_extension}")
        log.debug(f"Saving {len(json)} char to {self.filepath} ")
        with open(self.filepath, 'w', encoding='utf-8') as file:
            file.write(json)
        self.report(type={"INFO"}, message=f"Exported {len(cues)} to {self.filepath}")
        # cl: MouthCueList = props.cue_list

        return {'FINISHED'}


class ImportJsonCueList(bpy.types.Operator):
    """Import json file in the rhubarb-cli format"""

    bl_idname = "rhubarb.import_json_cue_list"
    bl_label = "Import from JSON"

    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    filter_glob: StringProperty(default='*.json;', options={'HIDDEN'})  # type: ignore

    @classmethod
    def disabled_reason(cls, context: Context) -> str:
        props = CaptureListProperties.capture_from_context(context)
        if not props:
            return "No capture selected"
        cl: MouthCueList = props.cue_list
        if len(cl.items) > 0:
            return "There are cues in the list. Clear the list first"
        return ""

    @classmethod
    def poll(cls, context: Context) -> bool:
        return ui_utils.validation_poll(cls, context)

    def invoke(self, context: Context, event) -> set:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: Context) -> set[str]:
        if not (self.filepath):
            return {'CANCELLED'}

        with open(self.filepath, 'r', encoding='utf-8') as file:
            json = file.read()
        log.debug(f"Parsing {len(json)} char from {self.filepath} ")
        json_parsed = RhubarbParser.parse_lipsync_json(json)
        cues = RhubarbParser.lipsync_json2MouthCues(json_parsed)
        log.debug(f"Parsed {len(cues)} adding them to the uilist")
        cprops = CaptureListProperties.capture_from_context(context)
        cl: MouthCueList = cprops.cue_list
        cl.add_cues(cues)

        self.report(type={"INFO"}, message=f"Imported {len(cues)} from {self.filepath}")
        # cl: MouthCueList = props.cue_list

        return {'FINISHED'}
