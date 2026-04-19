import bpy
from . import previews


class COMFY_UL_image_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            icon_id = previews.load_preview(item.filepath)
            if icon_id:
                layout.label(text=item.name, icon_value=icon_id)
            else:
                layout.label(text=item.name, icon="IMAGE")


class COMFY_PT_main_panel(bpy.types.Panel):
    """Main ComfyConnector panel in the 3D viewport sidebar"""
    bl_label = "ComfyUI"
    bl_idname = "COMFY_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ComfyUI"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Server:")
        layout.prop(scene, "comfy_server_url", text="")
        layout.operator("comfy.check_connection", icon="NETWORK_DRIVE")

        layout.separator()

        layout.label(text="Workflow:")
        layout.operator("comfy.load_workflow", icon="FILEBROWSER",
                        text=scene.comfy_workflow_path or "Select workflow JSON")

        if scene.comfy_inputs:
            layout.separator()
            layout.label(text="Inputs:")
            for item in scene.comfy_inputs:
                layout.prop(item, "value", text=item.label)

            layout.separator()
            layout.label(text="Output Folder:")
            layout.prop(scene, "comfy_output_dir", text="")

            layout.separator()
            row = layout.row(align=True)
            row.operator("comfy.run_workflow", icon="PLAY")
            row.operator("comfy.cancel_workflow", icon="X")

        if scene.comfy_images:
            layout.separator()
            layout.label(text="Generated Images:")
            layout.template_list(
                "COMFY_UL_image_list", "",
                scene, "comfy_images",
                scene, "comfy_active_image",
                rows=3,
            )
            row = layout.row(align=True)
            row.operator("comfy.set_background", icon="IMAGE_BACKGROUND")
            row.operator("comfy.apply_texture", icon="MATERIAL")


classes = [
    COMFY_UL_image_list,
    COMFY_PT_main_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
