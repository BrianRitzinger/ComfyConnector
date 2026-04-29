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


class COMFY_UL_camera_slot_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.prop(item, "camera", text="")
            scene = context.scene
            idx = item.image_index
            if scene.comfy_images and 0 <= idx < len(scene.comfy_images):
                row.label(text=scene.comfy_images[idx].name)
            else:
                row.label(text="—", icon="IMAGE")
            row.prop(item, "image_index", text="")


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
            layout.label(text="Control Image:")
            layout.prop(scene, "comfy_control_mode", text="")
            layout.operator("comfy.render_control", icon="RENDER_STILL")

            layout.separator()
            row = layout.row(align=True)
            row.operator("comfy.run_workflow", icon="PLAY")
            row.operator("comfy.cancel_workflow", icon="X")

        if scene.comfy_images:
            layout.separator()
            layout.label(text="Images:")
            layout.template_list(
                "COMFY_UL_image_list", "",
                scene, "comfy_images",
                scene, "comfy_active_image",
                rows=3,
            )
            layout.prop(scene, "comfy_icon_scale", text="Preview Size")
            active = scene.comfy_images[scene.comfy_active_image] if scene.comfy_images else None
            if active:
                icon_id = previews.load_preview(active.filepath)
                if icon_id:
                    layout.template_icon(icon_value=icon_id, scale=scene.comfy_icon_scale)
            row = layout.row(align=True)
            row.operator("comfy.set_background", icon="IMAGE_BACKGROUND")
            row.operator("comfy.apply_texture", icon="MATERIAL")
            row.operator("comfy.project_texture", icon="VIEW_CAMERA")
            layout.operator("comfy.bake_projection", icon="RENDER_STILL")
            layout.operator("comfy.set_control_image", icon="IMAGE_DATA")

        layout.separator()
        layout.label(text="Multi-Camera Projection:")
        layout.template_list(
            "COMFY_UL_camera_slot_list", "",
            scene, "comfy_camera_slots",
            scene, "comfy_active_camera_slot",
            rows=3,
        )
        row = layout.row(align=True)
        row.operator("comfy.add_camera_slot", icon="ADD", text="Add Slot")
        row.operator("comfy.remove_camera_slot", icon="REMOVE", text="Remove")
        if len(scene.comfy_camera_slots) >= 2:
            layout.operator("comfy.bake_multi_projection", icon="RENDER_STILL")


classes = [
    COMFY_UL_image_list,
    COMFY_UL_camera_slot_list,
    COMFY_PT_main_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
