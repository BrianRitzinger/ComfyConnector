import bpy
import json
from bpy.props import StringProperty
from . import comfy_api, previews


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

        if not scene.comfy_output_dir:
            self.report({"ERROR"}, "No output folder set")
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
        _start_polling(scene.comfy_server_url, prompt_id, scene.comfy_output_dir)
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


class COMFY_OT_set_background(bpy.types.Operator):
    """Set the selected image as the active camera background"""
    bl_idname = "comfy.set_background"
    bl_label = "Set as Cam Background"

    def execute(self, context):
        scene = context.scene
        if not scene.comfy_images:
            self.report({"ERROR"}, "No images available")
            return {"CANCELLED"}

        camera = scene.camera
        if not camera or camera.type != "CAMERA":
            self.report({"ERROR"}, "No active camera in scene")
            return {"CANCELLED"}

        item = scene.comfy_images[scene.comfy_active_image]
        image = bpy.data.images.load(item.filepath, check_existing=True)

        camera.data.show_background_images = True
        bg = camera.data.background_images.new()
        bg.image = image
        self.report({"INFO"}, f"Set camera background: {item.name}")
        return {"FINISHED"}


class COMFY_OT_apply_texture(bpy.types.Operator):
    """Apply the selected image as a texture on the active object"""
    bl_idname = "comfy.apply_texture"
    bl_label = "Apply as Texture"

    def execute(self, context):
        scene = context.scene
        obj = context.active_object

        if not scene.comfy_images:
            self.report({"ERROR"}, "No images available")
            return {"CANCELLED"}

        if not obj or not hasattr(obj.data, "materials"):
            self.report({"ERROR"}, "Select a mesh object first")
            return {"CANCELLED"}

        item = scene.comfy_images[scene.comfy_active_image]
        image = bpy.data.images.load(item.filepath, check_existing=True)

        if obj.data.materials:
            mat = obj.data.materials[0]
        else:
            mat = bpy.data.materials.new(name="ComfyMaterial")
            obj.data.materials.append(mat)

        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        tex_node = nodes.new("ShaderNodeTexImage")
        bsdf_node = nodes.new("ShaderNodeBsdfPrincipled")
        out_node = nodes.new("ShaderNodeOutputMaterial")

        tex_node.image = image
        tex_node.location = (-300, 0)
        bsdf_node.location = (0, 0)
        out_node.location = (300, 0)

        links.new(tex_node.outputs["Color"], bsdf_node.inputs["Base Color"])
        links.new(bsdf_node.outputs["BSDF"], out_node.inputs["Surface"])

        self.report({"INFO"}, f"Applied texture: {item.name}")
        return {"FINISHED"}


def _start_polling(server_url: str, prompt_id: str, output_dir: str):
    """Register a Blender timer to poll for workflow completion."""
    def poll():
        history = comfy_api.get_history(server_url, prompt_id)
        if history is None:
            return 2.0  # not done yet, check again in 2 seconds

        for node_outputs in history.get("outputs", {}).values():
            for img_info in node_outputs.get("images", []):
                if img_info.get("type") != "output":
                    continue
                filepath = comfy_api.download_image(server_url, img_info, output_dir)
                if not filepath:
                    continue
                scene = bpy.context.scene
                entry = scene.comfy_images.add()
                entry.name = img_info["filename"]
                entry.filepath = filepath
                entry.prompt_id = prompt_id
                previews.load_preview(filepath)

        for area in bpy.context.screen.areas:
            area.tag_redraw()

        return None  # stop timer

    bpy.app.timers.register(poll, first_interval=2.0)


classes = [
    COMFY_OT_check_connection,
    COMFY_OT_load_workflow,
    COMFY_OT_run_workflow,
    COMFY_OT_cancel_workflow,
    COMFY_OT_set_background,
    COMFY_OT_apply_texture,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
