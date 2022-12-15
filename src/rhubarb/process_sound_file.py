import bpy
import os
import subprocess
from typing import Optional, List
import logging
log = logging.getLogger(__name__)


class RhubarbCommandWrapper:
    """Wraps low level operations related to the lipsync executable."""

    def __init__(self, executable_path:str, recognizer="pocketSphinx"):
        self.executable_path = executable_path
        self.recognizer = recognizer
        self.process=None

    def verify(self) -> Optional[str]:
        if not self.executable_path:
            return "Configure the Rhubarb lipsync executable file path in the addon preferences. "
         # This is ugly, but Blender unpacks the zip without execute permission
        os.chmod(self.executable_path, 0o744)
        if not os.path.exists(self.executable_path) or os.isfile(self.executable_path):
            return f"The '{self.executable_path}' doesn't exists or is not a valid file."
        return None

    def build_command_args(self, input_file: str, dialog_file: Optional[str] = None):
        dialog = ["--dialogFile", dialog_file] if dialog_file else []
        return [self.executable_path,
                "-f", "json", 
                "--machineReadable", 
                "--extendedShapes", "GHX",
                "-r", self.recognizer,
                *dialog,
                input_file]

    def open_process(self, cmd_args:List[str]):
        assert self.verify() is None
        self.process = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True)



class ProcessSoundFile(bpy.types.Operator):
    bl_idname = "rhubarb.process_sound_file"
    bl_label = "Process the selected wav file with rhubarb executable"

    @classmethod
    def poll(cls, context):
        return True
