import bpy


class COMFY_PT_main_panel(bpy.types.Panel):
    """Main ComfyConnector panel in the 3D viewport sidebar"""
    bl_label = "ComfyUI"
    bl_idname = "COMFY_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ComfyUI"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Server:")
        layout.prop(context.scene, "comfy_server_url", text="")
        layout.operator("comfy.check_connection", icon="NETWORK_DRIVE")

        layout.separator()

        layout.label(text="Workflow:")
        layout.operator("comfy.load_workflow", icon="FILEBROWSER",
                        text=context.scene.comfy_workflow_path or "Select workflow JSON")

        if context.scene.comfy_inputs:
            layout.separator()
            layout.label(text="Inputs:")
            for item in context.scene.comfy_inputs:
                layout.prop(item, "value", text=item.label)

            layout.separator()
            row = layout.row(align=True)
            row.operator("comfy.run_workflow", icon="PLAY")
            row.operator("comfy.cancel_workflow", icon="X")


classes = [COMFY_PT_main_panel]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
