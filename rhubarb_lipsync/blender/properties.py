import bpy
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty
from bpy.types import Object, PropertyGroup, Scene

class CaptureProperties(PropertyGroup):

    sound : PointerProperty(type=bpy.types.Sound, name="Sound")
    fooProp: StringProperty(name="String Value3")
    
