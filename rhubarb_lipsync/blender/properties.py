import bpy
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty
from bpy.types import Object, PropertyGroup, Context, SoundSequence, Sound
from typing import Optional, cast


class CaptureProperties(PropertyGroup):

    sound: PointerProperty(type=bpy.types.Sound, name="Sound")
    start_frame: FloatProperty(name="Start frame", default=0)

    @staticmethod
    def from_context(ctx: Context) -> 'CaptureProperties':
        if not ctx.object:
            return None  # type: ignore
        # Seems to data-block properties are lazily created
        # and doesn't exists until accessed for the first time
        # if not 'rhubarb_lipsync' in self.ctx.active_object:
        try:
            p = ctx.object.rhubarb_lipsync  # type: ignore
        except AttributeError:
            return None  # type: ignore
        return p

    def find_strips_of_sound(self, context: Context, limit=0) -> list[SoundSequence]:
        '''Finds a sound strip which is using the selected sounds.'''
        exact_match: list[SoundSequence] = []
        name_match: list[SoundSequence] = []
        if not self.sound:
            return []

        for i, sq in enumerate(context.scene.sequence_editor.sequences_all):
            if limit > 0 and i > limit:
                break  # Limit reached, break the search (for performance reasons)
            if not hasattr(sq, "sound"):
                continue  # Not a sound strip
            ssq = cast(SoundSequence, sq)
            foundSnd = ssq.sound
            if foundSnd is None:
                continue  # An empty strip
            if self.sound == foundSnd:
                name_match += [ssq]
                continue
            if self.sound.filepath == foundSnd.filepath:
                name_match += [ssq]
        return exact_match + name_match  # Exact matches first
