import bpy
import urllib.request
import urllib.error
import json

COMFY_URL = "http://localhost:8188"


class COMFY_OT_check_connection(bpy.types.Operator):
    """Check if ComfyUI is running"""
    bl_idname = "comfy.check_connection"
    bl_label = "Check Connection"

    def execute(self, context):
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=3) as response:
                data = json.loads(response.read())
            self.report({"INFO"}, f"Connected to ComfyUI")
        except urllib.error.URLError:
            self.report({"ERROR"}, "Cannot reach ComfyUI — is it running on localhost:8188?")
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
        layout.label(text=f"Server: {COMFY_URL}")
        layout.operator("comfy.check_connection", icon="NETWORK_DRIVE")


classes = [
    COMFY_OT_check_connection,
    COMFY_PT_main_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
