from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context,Sound
from typing import Optional, List, Dict
from rhubarb_lipsync.blender.properties import CaptureProperties
import pathlib

log = logging.getLogger(__name__)

class CaptureMouthCuesPanel(bpy.types.Panel):
    
    bl_idname = 'RLPS_PT_capture_panel'
    bl_label = 'RLPS: Mouth cues capture'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RLSP"
    #bl_parent_id= 'VIEW3D_PT_example_panel'
    #bl_description = "Tool tip"
    #bl_context = "object"

    @property
    def props(self)->CaptureProperties:
        return self.ctx.active_object.rhubarb_lipsync

    def draw_error(self, msg:str):
        box = self.layout.box()
        box.label(text=msg, icon="ERROR")

    def validate_selection(self)->bool:
        assert self.ctx
        if not self.ctx.active_object:
            self.draw_error("Select an object")
            return False
        if not 'rhubarb_lipsync' in self.ctx.active_object:
            self.draw_error("Plugin not properly registered")
            self.draw_error("'rhubarb_lipsync' not found on the active object")
            return False
        return True

    def draw_sound_details(self, sound:Sound)->bool:
        layout=self.layout        
        layout.prop(sound, "filepath", text="")
        if sound.packed_file:            
            self.draw_error("Rhubarb requires a file on disk.")
            #self.draw_error("Please unpack the sound")
            return False        
        path=pathlib.Path(sound.filepath)
        if not path.exists:
            self.draw_error("Sound file doesn't exist.")
            return False
        box=layout.box()
        #line = layout.split()
        line = box.split()
        line.label(text="Sample rate")
        line.label(text=f"{sound.samplerate} Hz")
        line = box.split()
        
        line.label(text="File extension")
        
        line.label(text=path.suffix)
        if path.suffix.lower() not in ['.oggx', '.wav']:
            self.draw_error("Only wav or ogg supported")
            return False

        return True
    
    def draw(self, context:Context):
        try:            
            self.ctx=context
            if not self.validate_selection():
                return
            layout = self.layout            
            #layout.prop(self.props, "sound")            
            layout.template_ID(self.props, "sound", open="sound.open")
            if self.props.sound is None:
                self.draw_error("Select a sound file")
                return
            if not self.draw_sound_details(self.props.sound):
                return
            
            layout.operator(ProcessSoundFile.bl_idname)
        except Exception as e:
            self.draw_error("Unexpected error")
            self.draw_error(str(e))
            raise            
        finally:
            self.ctx=None
        

class ProcessSoundFile(bpy.types.Operator):
    bl_idname = "rhubarb.process_sound_file"
    bl_label = "Capture mouth cues"
    bl_description = "Process the selected sound file using the rhubarb executable"

    @classmethod
    def poll(cls, context):
        return True
