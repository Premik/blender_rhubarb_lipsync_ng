import bpy
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty
from bpy.types import Object, PropertyGroup, Scene

class LipsyncProperties(PropertyGroup):

    sound : PointerProperty(type=bpy.types.Sound)
    fooProp: StringProperty(name="String Value3")
    
