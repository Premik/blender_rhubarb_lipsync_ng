import bpy
import os
from subprocess import Popen, PIPE
from typing import Optional, List
import logging
log = logging.getLogger(__name__)


class RhubarbCommandWrapper:
    """Wraps low level operations related to the lipsync executable."""

    def __init__(self, executable_path:str, recognizer="pocketSphinx"):
        self.executable_path = executable_path
        self.recognizer = recognizer        
        self.process:Optional[Popen]=None
        self.lastOut=""
        self.lastErr=""

    def verify(self) -> Optional[str]:
        if not self.executable_path:
            return "Configure the Rhubarb lipsync executable file path in the addon preferences. "
         # This is ugly, but Blender unpacks the zip without execute permission
        
        if not os.path.exists(self.executable_path) or os.path.isfile(self.executable_path):
            return f"The '{self.executable_path}' doesn't exists or is not a valid file."
        os.chmod(self.executable_path, 0o744)
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

    def build_version_args(self):
        return [self.executable_path, "--version"]

    def open_process(self, cmd_args:List[str]):
        assert not self.running
        assert self.verify() is None
        self.lastOut=""
        self.lastErr=""
        self.process = Popen(cmd_args, stdout=PIPE, stderr=PIPE, universal_newlines=True)

    def close_process(self):
        if self.running:
            self.process.terminate()        
        self.process=None

    @property
    def running(self)->bool:
        return self.process is not None

    def communicate_with_process(self, timeout=0.1):
        assert self.running
        (stdout, stderr) = self.process.communicate(timeout=timeout)
        


class ProcessSoundFile(bpy.types.Operator):
    bl_idname = "rhubarb.process_sound_file"
    bl_label = "Process the selected wav file with rhubarb executable"

    @classmethod
    def poll(cls, context):
        return True
