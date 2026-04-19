import bpy
import json
from bpy.props import StringProperty
from . import comfy_api


class COMFY_OT_check_connection(bpy.types.Operator):
    """Check if ComfyUI is running"""
    bl_idname = "comfy.check_connection"
    bl_label = "Check Connection"

    def execute(self, context):
        error = comfy_api.check_connection(context.scene.comfy_server_url)
        if error:
            self.report({"ERROR"}, f"Cannot reach ComfyUI: {error}")
        else:
            self.report({"INFO"}, f"Connected to ComfyUI at {context.scene.comfy_server_url}")
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

        found = comfy_api.scan_workflow_inputs(workflow)
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


class COMFY_OT_run_workflow(bpy.types.Operator):
    """Submit the workflow to ComfyUI"""
    bl_idname = "comfy.run_workflow"
    bl_label = "Run Workflow"

    def execute(self, context):
        scene = context.scene

        if not scene.comfy_workflow_path:
            self.report({"ERROR"}, "No workflow loaded")
            return {"CANCELLED"}

        try:
            workflow = comfy_api.build_prompt(scene.comfy_workflow_path, scene.comfy_inputs)
        except Exception as e:
            self.report({"ERROR"}, f"Could not build workflow: {e}")
            return {"CANCELLED"}

        prompt_id, error = comfy_api.submit_prompt(scene.comfy_server_url, workflow)
        if error:
            self.report({"ERROR"}, f"Failed to submit workflow: {error}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Workflow queued — prompt_id: {prompt_id}")
        return {"FINISHED"}


class COMFY_OT_cancel_workflow(bpy.types.Operator):
    """Interrupt the currently running ComfyUI workflow"""
    bl_idname = "comfy.cancel_workflow"
    bl_label = "Cancel"

    def execute(self, context):
        error = comfy_api.interrupt(context.scene.comfy_server_url)
        if error:
            self.report({"ERROR"}, f"Could not cancel: {error}")
            return {"CANCELLED"}
        self.report({"INFO"}, "Sent interrupt to ComfyUI")
        return {"FINISHED"}


classes = [
    COMFY_OT_check_connection,
    COMFY_OT_load_workflow,
    COMFY_OT_run_workflow,
    COMFY_OT_cancel_workflow,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
