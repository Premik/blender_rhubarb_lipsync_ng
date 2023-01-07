import bpy

class ExamplePanel(bpy.types.Panel):
    
    bl_idname = 'VIEW3D_PT_example_panel'
    bl_label = 'Example Panel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    
    def draw(self, context):
        self.layout.label(text='Hello there3')
        self.layout.operator("object.testop", text="Test op")



class TestOpOperator(bpy.types.Operator):
    bl_idname = "object.testop"
    bl_label = "TestOp"

    def execute(self, context):
        print(f"{'RUN '*10}")
        return {'FINISHED'}


if __name__ == '__main__':
    bpy.utils.register_class(ExamplePanel)