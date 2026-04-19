import bpy
import urllib.request
import urllib.error
import json
from bpy.props import StringProperty

COMFY_URL_DEFAULT = "http://localhost:8188"


class COMFY_OT_check_connection(bpy.types.Operator):
    """Check if ComfyUI is running"""
    bl_idname = "comfy.check_connection"
    bl_label = "Check Connection"

    def execute(self, context):
        url = context.scene.comfy_server_url
        try:
            with urllib.request.urlopen(f"{url}/system_stats", timeout=3) as response:
                json.loads(response.read())
            self.report({"INFO"}, f"Connected to ComfyUI at {url}")
        except urllib.error.URLError:
            self.report({"ERROR"}, f"Cannot reach ComfyUI at {url}")
        return {"FINISHED"}


class COMFY_OT_load_workflow(bpy.types.Operator):
    """Open a file browser to select a ComfyUI workflow JSON"""
    bl_idname = "comfy.load_workflow"
    bl_label = "Load Workflow"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        context.scene.comfy_workflow_path = self.filepath
        self.report({"INFO"}, f"Loaded: {self.filepath}")
        return {"FINISHED"}


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


classes = [
    COMFY_OT_check_connection,
    COMFY_OT_load_workflow,
    COMFY_PT_main_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.comfy_server_url = StringProperty(
        name="Server URL",
        default=COMFY_URL_DEFAULT,
    )
    bpy.types.Scene.comfy_workflow_path = StringProperty(
        name="Workflow Path",
        subtype="FILE_PATH",
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.comfy_server_url
    del bpy.types.Scene.comfy_workflow_path


if __name__ == "__main__":
    register()
