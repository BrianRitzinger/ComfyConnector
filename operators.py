import bpy
import json
from bpy.props import StringProperty, EnumProperty
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
            entry.class_type = item["class_type"]

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
            workflow = comfy_api.build_prompt(scene.comfy_workflow_path, scene.comfy_inputs, scene.comfy_server_url)
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


class COMFY_OT_render_control(bpy.types.Operator):
    """Render a control image from the active camera for ControlNet"""
    bl_idname = "comfy.render_control"
    bl_label = "Render Control Image"

    def execute(self, context):
        import os
        scene = context.scene

        if not scene.comfy_output_dir:
            self.report({"ERROR"}, "No output folder set")
            return {"CANCELLED"}

        if not scene.camera:
            self.report({"ERROR"}, "No active camera in scene")
            return {"CANCELLED"}

        mode = scene.comfy_control_mode
        filename = f"control_{mode.lower()}.png"
        output_path = os.path.join(bpy.path.abspath(scene.comfy_output_dir), filename)

        orig_filepath = scene.render.filepath
        orig_format = scene.render.image_settings.file_format

        try:
            scene.render.filepath = output_path
            scene.render.image_settings.file_format = 'PNG'

            if mode == 'NORMAL':
                _render_normal_map(scene)
            else:
                bpy.ops.render.render(write_still=True)

            scene.comfy_control_path = output_path
            for item in scene.comfy_inputs:
                if item.class_type == "LoadImage":
                    item.value = output_path
            self.report({"INFO"}, f"Control image saved: {filename}")

        except Exception as e:
            self.report({"ERROR"}, f"Render failed: {e}")
            return {"CANCELLED"}

        finally:
            scene.render.filepath = orig_filepath
            scene.render.image_settings.file_format = orig_format

        return {"FINISHED"}


def _render_normal_map(scene):
    """Render world-space normals by temporarily overriding all mesh materials."""
    # Build an emission material that outputs world-space normals as 0-1 color
    mat = bpy.data.materials.new("_comfy_normal_temp")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    geo    = nodes.new("ShaderNodeNewGeometry")
    scale  = nodes.new("ShaderNodeVectorMath")
    scale.operation = 'SCALE'
    scale.inputs['Scale'].default_value = 0.5
    add    = nodes.new("ShaderNodeVectorMath")
    add.operation = 'ADD'
    add.inputs[1].default_value = (0.5, 0.5, 0.5)
    emit   = nodes.new("ShaderNodeEmission")
    out    = nodes.new("ShaderNodeOutputMaterial")

    links.new(geo.outputs['Normal'],   scale.inputs['Vector'])
    links.new(scale.outputs['Vector'], add.inputs[0])
    links.new(add.outputs['Vector'],   emit.inputs['Color'])
    links.new(emit.outputs['Emission'], out.inputs['Surface'])

    # Save and replace materials on every mesh
    saved = {}
    for obj in scene.objects:
        if obj.type == 'MESH':
            saved[obj.name] = list(obj.data.materials)
            obj.data.materials.clear()
            obj.data.materials.append(mat)

    try:
        bpy.ops.render.render(write_still=True)
    finally:
        for obj in scene.objects:
            if obj.type == 'MESH' and obj.name in saved:
                obj.data.materials.clear()
                for m in saved[obj.name]:
                    obj.data.materials.append(m)
        bpy.data.materials.remove(mat)


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


class COMFY_OT_project_texture(bpy.types.Operator):
    """Project the selected image onto the active object from the camera's viewpoint"""
    bl_idname = "comfy.project_texture"
    bl_label = "Project from Camera"

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

        mat = bpy.data.materials.new(name=f"ComfyProjection_{item.name}")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        coord_node = nodes.new("ShaderNodeTexCoord")
        tex_node = nodes.new("ShaderNodeTexImage")
        bsdf_node = nodes.new("ShaderNodeBsdfPrincipled")
        out_node = nodes.new("ShaderNodeOutputMaterial")

        coord_node.location = (-600, 0)
        tex_node.location = (-300, 0)
        bsdf_node.location = (0, 0)
        out_node.location = (300, 0)

        tex_node.image = image

        # Window coordinates map exactly to the render camera's screen space (0-1),
        # so the AI image — generated from that same view — projects back correctly.
        links.new(coord_node.outputs["Window"], tex_node.inputs["Vector"])
        links.new(tex_node.outputs["Color"], bsdf_node.inputs["Base Color"])
        links.new(bsdf_node.outputs["BSDF"], out_node.inputs["Surface"])

        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

        self.report({"INFO"}, f"Projection material set on '{obj.name}' — look through camera (Numpad 0) to preview")
        return {"FINISHED"}


class COMFY_OT_bake_projection(bpy.types.Operator):
    """Bake the camera-projected texture into the mesh UV map (requires Cycles)"""
    bl_idname = "comfy.bake_projection"
    bl_label = "Bake Projection to UV"

    resolution: EnumProperty(
        name="Resolution",
        items=[
            ('512',  '512 px',  ''),
            ('1024', '1024 px', ''),
            ('2048', '2048 px', ''),
            ('4096', '4096 px', ''),
        ],
        default='2048',
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "resolution")

    def execute(self, context):
        import os
        scene = context.scene
        obj = context.active_object

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object first")
            return {'CANCELLED'}

        if not obj.data.materials or not obj.data.materials[0]:
            self.report({'ERROR'}, "No material — run 'Project from Camera' first")
            return {'CANCELLED'}

        source_img = next(
            (n.image for n in obj.data.materials[0].node_tree.nodes
             if n.type == 'TEX_IMAGE' and n.image),
            None
        )
        if not source_img:
            self.report({'ERROR'}, "No image texture in material — run 'Project from Camera' first")
            return {'CANCELLED'}

        if not scene.camera:
            self.report({'ERROR'}, "No active camera in scene")
            return {'CANCELLED'}

        if not scene.comfy_output_dir:
            self.report({'ERROR'}, "No output folder set")
            return {'CANCELLED'}

        orig_engine = scene.render.engine
        scene.render.engine = 'CYCLES'
        mesh = obj.data

        # Auto-create UV map if the mesh has none
        if not mesh.uv_layers:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
            bpy.ops.object.mode_set(mode='OBJECT')

        uv_layer_name = mesh.uv_layers.active.name

        # UV Project modifier: drives the active UV layer from camera space during baking.
        # This is needed because Window texture coordinates don't work correctly during
        # baking (Blender shoots rays from the mesh, not from the camera viewpoint).
        uv_mod = obj.modifiers.new("_comfy_uvproj_temp", 'UV_PROJECT')
        uv_mod.uv_layer = uv_layer_name
        uv_mod.projectors[0].object = scene.camera
        rx, ry = scene.render.resolution_x, scene.render.resolution_y
        if rx >= ry:
            uv_mod.aspect_x = rx / ry
            uv_mod.aspect_y = 1.0
        else:
            uv_mod.aspect_x = 1.0
            uv_mod.aspect_y = ry / rx

        # Temporary emission material: UV-sampled source image → Emission.
        # Emission + Emit bake captures raw colour with zero lighting influence,
        # avoiding the "dark bake" problem caused by Combined or lit Diffuse bakes.
        bake_mat = bpy.data.materials.new("_comfy_bake_temp")
        bake_mat.use_nodes = True
        bm_nodes = bake_mat.node_tree.nodes
        bm_links = bake_mat.node_tree.links
        bm_nodes.clear()

        bm_tex = bm_nodes.new('ShaderNodeTexImage')
        bm_tex.image = source_img
        bm_tex.location = (-300, 100)

        bm_emit = bm_nodes.new('ShaderNodeEmission')
        bm_emit.location = (0, 100)

        bm_out = bm_nodes.new('ShaderNodeOutputMaterial')
        bm_out.location = (300, 100)

        bm_links.new(bm_tex.outputs['Color'], bm_emit.inputs['Color'])
        bm_links.new(bm_emit.outputs['Emission'], bm_out.inputs['Surface'])

        # Bake target: Image Texture node that is selected + active but NOT connected.
        # Blender writes the bake result into whichever image node is active.
        size = int(self.resolution)
        img_name = f"ComfyBake_{obj.name}"
        if img_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[img_name])
        bake_img = bpy.data.images.new(img_name, width=size, height=size)

        bake_node = bm_nodes.new('ShaderNodeTexImage')
        bake_node.image = bake_img
        bake_node.location = (-300, -200)
        for n in bm_nodes:
            n.select = False
        bake_node.select = True
        bm_nodes.active = bake_node

        original_mat = obj.data.materials[0]
        obj.data.materials[0] = bake_mat

        try:
            scene.render.bake.margin = 16
            bpy.ops.object.bake(type='EMIT')

            out_path = os.path.join(bpy.path.abspath(scene.comfy_output_dir), f"{img_name}.png")
            bake_img.filepath_raw = out_path
            bake_img.file_format = 'PNG'
            bake_img.save()

        except Exception as e:
            self.report({'ERROR'}, f"Bake failed: {e}")
            obj.data.materials[0] = original_mat
            bpy.data.materials.remove(bake_mat)
            obj.modifiers.remove(uv_mod)
            scene.render.engine = orig_engine
            return {'CANCELLED'}

        finally:
            obj.modifiers.remove(uv_mod)
            scene.render.engine = orig_engine

        # Replace the projection material with a clean UV-mapped material
        # using the baked image — now view-independent and ready to export.
        final_mat = bpy.data.materials.new(f"ComfyBaked_{obj.name}")
        final_mat.use_nodes = True
        fn = final_mat.node_tree.nodes
        fl = final_mat.node_tree.links
        fn.clear()

        f_tex = fn.new('ShaderNodeTexImage')
        f_tex.image = bake_img
        f_tex.location = (-300, 0)

        f_bsdf = fn.new('ShaderNodeBsdfPrincipled')
        f_bsdf.location = (0, 0)

        f_out = fn.new('ShaderNodeOutputMaterial')
        f_out.location = (300, 0)

        fl.new(f_tex.outputs['Color'], f_bsdf.inputs['Base Color'])
        fl.new(f_bsdf.outputs['BSDF'], f_out.inputs['Surface'])

        obj.data.materials[0] = final_mat
        bpy.data.materials.remove(bake_mat)

        self.report({'INFO'}, f"Baked to '{img_name}.png' and applied as UV material")
        return {'FINISHED'}


class COMFY_OT_add_camera_slot(bpy.types.Operator):
    """Add a camera/image slot for multi-camera projection"""
    bl_idname = "comfy.add_camera_slot"
    bl_label = "Add Camera Slot"

    def execute(self, context):
        context.scene.comfy_camera_slots.add()
        return {'FINISHED'}


class COMFY_OT_remove_camera_slot(bpy.types.Operator):
    """Remove the selected camera/image slot"""
    bl_idname = "comfy.remove_camera_slot"
    bl_label = "Remove Camera Slot"

    def execute(self, context):
        scene = context.scene
        idx = scene.comfy_active_camera_slot
        if 0 <= idx < len(scene.comfy_camera_slots):
            scene.comfy_camera_slots.remove(idx)
            scene.comfy_active_camera_slot = max(0, idx - 1)
        return {'FINISHED'}


class COMFY_OT_bake_multi_projection(bpy.types.Operator):
    """Bake blended camera projections into a single UV-mapped texture (requires Cycles)"""
    bl_idname = "comfy.bake_multi_projection"
    bl_label = "Bake Multi-Camera Projection"

    resolution: EnumProperty(
        name="Resolution",
        items=[
            ('512',  '512 px',  ''),
            ('1024', '1024 px', ''),
            ('2048', '2048 px', ''),
            ('4096', '4096 px', ''),
        ],
        default='2048',
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "resolution")

    def execute(self, context):
        import os
        from mathutils import Vector

        scene = context.scene
        obj = context.active_object
        slots = scene.comfy_camera_slots

        if len(slots) < 2:
            self.report({'ERROR'}, "Add at least 2 camera slots")
            return {'CANCELLED'}

        for i, slot in enumerate(slots):
            if not slot.camera:
                self.report({'ERROR'}, f"Slot {i + 1}: no camera assigned")
                return {'CANCELLED'}
            if not (0 <= slot.image_index < len(scene.comfy_images)):
                self.report({'ERROR'}, f"Slot {i + 1}: image index out of range")
                return {'CANCELLED'}

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object first")
            return {'CANCELLED'}

        if not scene.comfy_output_dir:
            self.report({'ERROR'}, "No output folder set")
            return {'CANCELLED'}

        orig_engine = scene.render.engine
        scene.render.engine = 'CYCLES'
        mesh = obj.data
        rx, ry = scene.render.resolution_x, scene.render.resolution_y
        N = len(slots)

        # --- UV layers: one per camera (for projection), one for the bake target ---
        proj_uv_layers = []
        for i in range(N):
            name = f"ComfyProj_{i}"
            layer = mesh.uv_layers.get(name) or mesh.uv_layers.new(name=name)
            proj_uv_layers.append(layer)

        bake_uv_name = "ComfyBakeUV"
        bake_uv = mesh.uv_layers.get(bake_uv_name)
        if not bake_uv:
            bake_uv = mesh.uv_layers.new(name=bake_uv_name)
            mesh.uv_layers.active = bake_uv
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
            bpy.ops.object.mode_set(mode='OBJECT')

        # --- UV Project modifiers: one per camera, writing to ComfyProj_i ---
        uv_mods = []
        for i, slot in enumerate(slots):
            mod = obj.modifiers.new(f"_comfy_uvproj_{i}", 'UV_PROJECT')
            mod.uv_layer = proj_uv_layers[i].name
            mod.projectors[0].object = slot.camera
            if rx >= ry:
                mod.aspect_x = rx / ry
                mod.aspect_y = 1.0
            else:
                mod.aspect_x = 1.0
                mod.aspect_y = ry / rx
            uv_mods.append(mod)

        # Pre-compute each camera's world-space forward direction (into the scene = -Z).
        # These are baked as constants into the shader because the camera doesn't move
        # during the bake pass.
        cam_forwards = []
        for slot in slots:
            fwd = -(slot.camera.matrix_world.col[2].to_3d().normalized())
            cam_forwards.append(tuple(fwd))

        source_images = []
        for slot in slots:
            entry = scene.comfy_images[slot.image_index]
            source_images.append(bpy.data.images.load(entry.filepath, check_existing=True))

        # --- Build temporary emission material with normal-weighted blend ---
        bake_mat = bpy.data.materials.new("_comfy_multi_bake_temp")
        bake_mat.use_nodes = True
        nodes = bake_mat.node_tree.nodes
        links = bake_mat.node_tree.links
        nodes.clear()

        col_x, row_h = -1400, 160

        geo = nodes.new('ShaderNodeNewGeometry')
        geo.location = (col_x, 0)

        # Per-camera: clamp(dot(face_normal, cam_forward), 0, inf)
        raw_weight_sockets = []
        for i, fwd in enumerate(cam_forwards):
            dot = nodes.new('ShaderNodeVectorMath')
            dot.operation = 'DOT_PRODUCT'
            dot.inputs[1].default_value = fwd
            dot.location = (col_x + 200, -i * row_h)
            links.new(geo.outputs['Normal'], dot.inputs[0])

            clamp = nodes.new('ShaderNodeMath')
            clamp.operation = 'MAXIMUM'
            clamp.inputs[1].default_value = 0.0
            clamp.location = (col_x + 400, -i * row_h)
            links.new(dot.outputs['Value'], clamp.inputs[0])
            raw_weight_sockets.append(clamp.outputs['Value'])

        # Sum raw weights
        total = raw_weight_sockets[0]
        for i in range(1, N):
            add = nodes.new('ShaderNodeMath')
            add.operation = 'ADD'
            add.location = (col_x + 600, -i * 80)
            links.new(total, add.inputs[0])
            links.new(raw_weight_sockets[i], add.inputs[1])
            total = add.outputs['Value']

        # Guard against all-zero (face points away from every camera)
        safe = nodes.new('ShaderNodeMath')
        safe.operation = 'MAXIMUM'
        safe.inputs[1].default_value = 0.001
        safe.location = (col_x + 800, 80)
        links.new(total, safe.inputs[0])

        # Normalize
        norm_sockets = []
        for i, raw in enumerate(raw_weight_sockets):
            div = nodes.new('ShaderNodeMath')
            div.operation = 'DIVIDE'
            div.location = (col_x + 800, -i * row_h)
            links.new(raw, div.inputs[0])
            links.new(safe.outputs['Value'], div.inputs[1])
            norm_sockets.append(div.outputs['Value'])

        # Per-camera: sample image via projected UV, scale by normalized weight
        # VectorMath SCALE avoids ShaderNodeMixRGB / ShaderNodeMix API differences
        weighted_sockets = []
        for i, (img, uv_layer, norm_w) in enumerate(zip(source_images, proj_uv_layers, norm_sockets)):
            uv_node = nodes.new('ShaderNodeUVMap')
            uv_node.uv_map = uv_layer.name
            uv_node.location = (col_x + 1000, -i * row_h)

            tex = nodes.new('ShaderNodeTexImage')
            tex.image = img
            tex.location = (col_x + 1200, -i * row_h)
            links.new(uv_node.outputs['UV'], tex.inputs['Vector'])

            scale = nodes.new('ShaderNodeVectorMath')
            scale.operation = 'SCALE'
            scale.location = (col_x + 1500, -i * row_h)
            links.new(tex.outputs['Color'], scale.inputs['Vector'])
            links.new(norm_w, scale.inputs['Scale'])
            weighted_sockets.append(scale.outputs['Vector'])

        # Sum all weighted colours
        result = weighted_sockets[0]
        for i in range(1, N):
            add = nodes.new('ShaderNodeVectorMath')
            add.operation = 'ADD'
            add.location = (col_x + 1700, -i * 80)
            links.new(result, add.inputs[0])
            links.new(weighted_sockets[i], add.inputs[1])
            result = add.outputs['Vector']

        emit = nodes.new('ShaderNodeEmission')
        emit.location = (col_x + 1900, 0)
        links.new(result, emit.inputs['Color'])

        mat_out = nodes.new('ShaderNodeOutputMaterial')
        mat_out.location = (col_x + 2100, 0)
        links.new(emit.outputs['Emission'], mat_out.inputs['Surface'])

        # Bake target: Image Texture node that is selected + active, NOT connected
        size = int(self.resolution)
        img_name = f"ComfyMultiBake_{obj.name}"
        if img_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[img_name])
        bake_img = bpy.data.images.new(img_name, width=size, height=size)

        bake_node = nodes.new('ShaderNodeTexImage')
        bake_node.image = bake_img
        bake_node.location = (col_x + 1000, -N * row_h - 100)
        for n in nodes:
            n.select = False
        bake_node.select = True
        nodes.active = bake_node

        original_mat = obj.data.materials[0] if obj.data.materials else None
        if obj.data.materials:
            obj.data.materials[0] = bake_mat
        else:
            obj.data.materials.append(bake_mat)

        mesh.uv_layers.active = bake_uv

        try:
            scene.render.bake.margin = 16
            bpy.ops.object.bake(type='EMIT')

            out_path = os.path.join(
                bpy.path.abspath(scene.comfy_output_dir),
                f"{img_name}.png",
            )
            bake_img.filepath_raw = out_path
            bake_img.file_format = 'PNG'
            bake_img.save()

        except Exception as e:
            self.report({'ERROR'}, f"Bake failed: {e}")
            obj.data.materials[0] = original_mat
            bpy.data.materials.remove(bake_mat)
            for mod in uv_mods:
                obj.modifiers.remove(mod)
            scene.render.engine = orig_engine
            return {'CANCELLED'}

        finally:
            for mod in uv_mods:
                obj.modifiers.remove(mod)
            scene.render.engine = orig_engine

        # Apply final UV-mapped material using the baked image
        final_mat = bpy.data.materials.new(f"ComfyMultiBaked_{obj.name}")
        final_mat.use_nodes = True
        fn = final_mat.node_tree.nodes
        fl = final_mat.node_tree.links
        fn.clear()

        f_uv = fn.new('ShaderNodeUVMap')
        f_uv.uv_map = bake_uv_name
        f_uv.location = (-600, 0)

        f_tex = fn.new('ShaderNodeTexImage')
        f_tex.image = bake_img
        f_tex.location = (-300, 0)

        f_bsdf = fn.new('ShaderNodeBsdfPrincipled')
        f_bsdf.location = (0, 0)

        f_out = fn.new('ShaderNodeOutputMaterial')
        f_out.location = (300, 0)

        fl.new(f_uv.outputs['UV'], f_tex.inputs['Vector'])
        fl.new(f_tex.outputs['Color'], f_bsdf.inputs['Base Color'])
        fl.new(f_bsdf.outputs['BSDF'], f_out.inputs['Surface'])

        obj.data.materials[0] = final_mat
        bpy.data.materials.remove(bake_mat)

        self.report({'INFO'}, f"Multi-projection baked to '{img_name}.png' — UV material applied")
        return {'FINISHED'}


def _start_polling(server_url: str, prompt_id: str, output_dir: str):
    """Register a Blender timer to poll for workflow completion."""
    # TODO: add a max-poll-count or wall-clock timeout so the timer stops if
    # ComfyUI never completes the prompt (e.g. queue stall, server crash).
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
    COMFY_OT_render_control,
    COMFY_OT_check_connection,
    COMFY_OT_load_workflow,
    COMFY_OT_run_workflow,
    COMFY_OT_cancel_workflow,
    COMFY_OT_set_background,
    COMFY_OT_apply_texture,
    COMFY_OT_project_texture,
    COMFY_OT_bake_projection,
    COMFY_OT_add_camera_slot,
    COMFY_OT_remove_camera_slot,
    COMFY_OT_bake_multi_projection,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
