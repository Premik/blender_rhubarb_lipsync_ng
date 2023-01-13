import bpy

bl_info = {
    'name': 'Rhubarb Lipsync',
    'author': 'Addon by Andrew Charlton, Rewrite by Premysl S. includes Rhubarb Lip Sync by Daniel S. Wolf',
    'version': (4, 0, 0),
    'blender': (3, 40, 0),
    'location': 'Properties > Armature',
    'description': 'Integrate Rhubarb Lipsync into Blender',
    'wiki_url': 'https://github.com/Premik/blender-rhubarb-lipsync',
    'tracker_url': 'https://github.com/Premik/blender-rhubarb-lipsync/issues',
    'support': 'COMMUNITY',
    'category': 'Animation',
}



import rhubarb_lipsync.blender.auto_load
rhubarb_lipsync.blender.auto_load.init(__file__)

def register():
    rhubarb_lipsync.blender.auto_load.register()
 
def unregister():
    rhubarb_lipsync.blender.auto_load.unregister()

#from rhubarb_lipsync.blender.testing_panel import ExamplePanel, TestOpOperator
#from rhubarb_lipsync.blender.properties import LipsyncProperties

#register2, unregister = bpy.utils.register_classes_factory([LipsyncProperties, ExamplePanel, TestOpOperator])

#from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty
#def register():
#    register2()
#    bpy.types.Object.rhubarb_lipsync=PointerProperty(type=LipsyncProperties)    
 

 
