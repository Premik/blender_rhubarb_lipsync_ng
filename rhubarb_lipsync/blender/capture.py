from io import TextIOWrapper
import logging
import bpy
from bpy.types import Context,Sound,SoundSequence
from typing import Optional, List, Dict, cast
from rhubarb_lipsync.blender.properties import CaptureProperties
import pathlib

log = logging.getLogger(__name__)

def context_selection_validation(ctx:Context)->str:
    if not ctx.object:
        return "No active object selected"
    if not CaptureProperties.from_context(ctx):
        return "'rhubarb_lipsync' not found on the active object"
    return ""

class CaptureMouthCuesPanel(bpy.types.Panel):
    
    bl_idname = 'RLPS_PT_capture_panel'
    bl_label = 'RLPS: Mouth cues capture'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RLSP"
    #bl_parent_id= 'VIEW3D_PT_example_panel'
    #bl_description = "Tool tip"
    #bl_context = "object"

   

    def draw_error(self, msg:str):
        box = self.layout.box()
        box.label(text=msg, icon="ERROR")
    
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
        line.label(text="Channels")
        line.label(text=str(sound.channels))
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
            layout = self.layout            
            layout.operator(PlaceSoundOnStrip.bl_idname)
            selection_error=context_selection_validation(context)
            if selection_error:
                self.draw_error(selection_error)
                return
            
            #layout.prop(self.props, "sound")
            props=CaptureProperties.from_context(self.ctx)
            assert props
            layout.template_ID(props, "sound", open="sound.open")
            if props.sound is None:
                self.draw_error("Select a sound file")
                return
            if not self.draw_sound_details(props.sound):
                return
            
            layout.operator(ProcessSoundFile.bl_idname)
        except Exception as e:
            self.draw_error("Unexpected error")
            self.draw_error(str(e))
            raise            
        finally:
            self.ctx=None # type: ignore


#bpy.ops.sequencer.sound_strip_add(
# filepath="/tmp/work/1.flac", directory="/tmp/work/", 
# files=[{"name":"1.flac", "name":"1.flac"}], 
# frame_start=23, channel=1, 
# overlap_shuffle_override=True)

#C.active_sequence_strip
# bpy.data.scenes['Scene'].sequence_editor.sequences_all["en_male_electricity.ogg"]

class PlaceSoundOnStrip(bpy.types.Operator):
    bl_idname = "rhubarb.place_sound_on_strip"
    bl_label = "Place on strip"
    bl_description = "Place the sound on a sound strip."
    bl_options = {'UNDO', 'INTERNAL'}

    @classmethod
    def disabled_reason(cls, context:Context)->str:
        selection_error=context_selection_validation(context)
        if selection_error: return selection_error
        props=CaptureProperties.from_context(context)
        if not props.sound: return "No sound selected"
        if props.find_strip_of_sound(context):
            return f"Already placed on a strip"
        return ""

    @classmethod
    def poll(cls, context:Context)->bool:
        m = cls.disabled_reason(context)
        if not m: return True
        # Following is not a class method per doc. But seems to work like it
        cls.poll_message_set(m) # type: ignore
        return False

class ProcessSoundFile(bpy.types.Operator):
    bl_idname = "rhubarb.process_sound_file"
    bl_label = "Capture mouth cues"
    bl_description = "Process the selected sound file using the rhubarb executable"

    @classmethod
    def poll(cls, context):
        return True
