import bpy
import urllib.request
import urllib.error
import json
from bpy.props import StringProperty, CollectionProperty
from bpy.types import PropertyGroup

COMFY_URL_DEFAULT = "http://localhost:8188"
CC_PREFIX = "[CC]"


class ComfyInput(PropertyGroup):
    """Stores one [CC] tagged input from the workflow"""
    node_id: StringProperty()
    input_key: StringProperty()
    label: StringProperty()
    value: StringProperty()


def scan_workflow_inputs(workflow: dict) -> list[dict]:
    """Return list of {node_id, input_key, label} for all [CC] tagged nodes."""
    inputs = []
    for node_id, node in workflow.items():
        title = node.get("_meta", {}).get("title", "")
        if CC_PREFIX not in title:
            continue
        label = title.replace(CC_PREFIX, "").strip()
        node_inputs = node.get("inputs", {})
        for key, value in node_inputs.items():
            if isinstance(value, list):
                continue  # skip node links, only expose plain values
            inputs.append({
                "node_id": node_id,
                "input_key": key,
                "label": f"{label} — {key}",
                "value": str(value),
            })
    return inputs


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
        try:
            with open(self.filepath, "r") as f:
                workflow = json.load(f)
        except Exception as e:
            self.report({"ERROR"}, f"Could not read workflow: {e}")
            return {"CANCELLED"}

        context.scene.comfy_workflow_path = self.filepath
        context.scene.comfy_inputs.clear()

        found = scan_workflow_inputs(workflow)
        for item in found:
            entry = context.scene.comfy_inputs.add()
            entry.node_id = item["node_id"]
            entry.input_key = item["input_key"]
            entry.label = item["label"]
            entry.value = item["value"]

        if found:
            self.report({"INFO"}, f"Loaded {len(found)} [CC] input(s) from workflow")
        else:
            self.report({"WARNING"}, "No [CC] tagged nodes found in workflow")
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

        if context.scene.comfy_inputs:
            layout.separator()
            layout.label(text="Inputs:")
            for item in context.scene.comfy_inputs:
                layout.prop(item, "value", text=item.label)


classes = [
    ComfyInput,
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
    bpy.types.Scene.comfy_inputs = CollectionProperty(type=ComfyInput)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.comfy_server_url
    del bpy.types.Scene.comfy_workflow_path
    del bpy.types.Scene.comfy_inputs


if __name__ == "__main__":
    register()
