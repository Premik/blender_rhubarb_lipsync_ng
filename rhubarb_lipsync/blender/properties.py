import bpy
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty
from bpy.types import Object, PropertyGroup, Context, SoundSequence
from typing import Optional, cast

class CaptureProperties(PropertyGroup):

    sound : PointerProperty(type=bpy.types.Sound, name="Sound")
    start_frame: FloatProperty(name="Start frame", default=0)

    @staticmethod
    def from_context(ctx:Context)->Optional['CaptureProperties']:
        if not ctx.object: return None
        # Seems to data-block properties are lazily created 
        # and doesn't exists until accessed for the first time
        #if not 'rhubarb_lipsync' in self.ctx.active_object:
        try: p=ctx.object.rhubarb_lipsync # type: ignore
        except AttributeError: return None
        return p

    def find_strip_of_sound(self, context:Context)->Optional[SoundSequence]:
        '''Finds a sound strip which is using the selected sounds.'''
        if not self.sound: return None        
        for sq in context.scene.sequence_editor.sequences_all:
            if not hasattr(sq, "sound"): continue #Not a sound strip
            ssq=cast(SoundSequence, sq)
            foundSnd=ssq.sound
            if self.sound == foundSnd: return ssq
        return None
    
