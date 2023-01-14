import bpy
from bpy.props import FloatProperty, StringProperty, BoolProperty, PointerProperty
from rhubarb_lipsync.blender.properties import CaptureProperties
import pathlib

class ExamplePanel(bpy.types.Panel):
    
    bl_idname = 'VIEW3D_PT_example_panel'
    bl_label = 'Example Panel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RLSP"
    
    def draw(self, context):
        self.layout.label(text='Hello there11')
        self.layout.operator(TestOpOperator.bl_idname, text="Test op")
        

class TestOpOperator(bpy.types.Operator): 
    bl_idname = "object.testop"
    bl_label = "TestOp"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Tool tip on op"

    
    #sound : PointerProperty(type=bpy.types.Sound)
    #pp : PointerProperty(type=LipsyncProperties)
    direction: StringProperty(name="String Value2")

    def execute(self, context):
        print(f"{'RUN '*10}")
        import rhubarb_lipsync.blender.auto_load        
        p = pathlib.Path(__file__).parent
        rhubarb_lipsync.blender.auto_load.init(str(p))

        return {'FINISHED'}
