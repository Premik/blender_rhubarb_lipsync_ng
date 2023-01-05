from io import TextIOWrapper
import bpy

log = logging.getLogger(__name__)

class ProcessSoundFile(bpy.types.Operator):
    bl_idname = "rhubarb.process_sound_file"
    bl_label = "Process the selected wav file with rhubarb executable"

    @classmethod
    def poll(cls, context):
        return True
