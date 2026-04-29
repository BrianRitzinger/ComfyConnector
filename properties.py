import bpy
from bpy.props import StringProperty, CollectionProperty, IntProperty, EnumProperty, PointerProperty
from bpy.types import PropertyGroup
from .comfy_api import COMFY_URL_DEFAULT


class ComfyCameraSlot(PropertyGroup):
    """One camera + image pair for multi-camera projection baking"""
    camera: PointerProperty(
        name="Camera",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'CAMERA',
    )
    image_index: IntProperty(name="Img #", default=0, min=0)


class ComfyInput(PropertyGroup):
    """Stores one [CC] tagged input from the workflow"""
    node_id: StringProperty()
    input_key: StringProperty()
    label: StringProperty()
    value: StringProperty()
    class_type: StringProperty()


class ComfyImage(PropertyGroup):
    """Stores one generated image"""
    name: StringProperty()
    filepath: StringProperty(subtype="FILE_PATH")
    prompt_id: StringProperty()


def register():
    bpy.utils.register_class(ComfyCameraSlot)
    bpy.utils.register_class(ComfyInput)
    bpy.utils.register_class(ComfyImage)
    bpy.types.Scene.comfy_server_url = StringProperty(
        name="Server URL",
        default=COMFY_URL_DEFAULT,
    )
    bpy.types.Scene.comfy_workflow_path = StringProperty(
        name="Workflow Path",
        subtype="FILE_PATH",
    )
    bpy.types.Scene.comfy_output_dir = StringProperty(
        name="Output Folder",
        subtype="DIR_PATH",
        default="",
    )
    bpy.types.Scene.comfy_inputs = CollectionProperty(type=ComfyInput)
    bpy.types.Scene.comfy_images = CollectionProperty(type=ComfyImage)
    bpy.types.Scene.comfy_active_image = IntProperty(name="Active Image", default=0)
    bpy.types.Scene.comfy_icon_scale = IntProperty(
        name="Preview Size",
        default=8,
        min=2,
        max=20,
    )
    bpy.types.Scene.comfy_control_mode = EnumProperty(
        name="Control Mode",
        items=[
            ('NORMAL', 'Normal Map', 'Render surface normals — use with normal ControlNet models'),
            ('RENDER', 'Full Render', 'Render using current scene settings — use ComfyUI preprocessors for depth/canny'),
        ],
        default='NORMAL',
    )
    bpy.types.Scene.comfy_control_path = StringProperty(
        name="Control Image Path",
        subtype="FILE_PATH",
        default="",
    )
    bpy.types.Scene.comfy_camera_slots = CollectionProperty(type=ComfyCameraSlot)
    bpy.types.Scene.comfy_active_camera_slot = IntProperty(default=0)


def unregister():
    bpy.utils.unregister_class(ComfyCameraSlot)
    bpy.utils.unregister_class(ComfyInput)
    bpy.utils.unregister_class(ComfyImage)
    del bpy.types.Scene.comfy_server_url
    del bpy.types.Scene.comfy_workflow_path
    del bpy.types.Scene.comfy_output_dir
    del bpy.types.Scene.comfy_inputs
    del bpy.types.Scene.comfy_images
    del bpy.types.Scene.comfy_active_image
    del bpy.types.Scene.comfy_icon_scale
    del bpy.types.Scene.comfy_control_mode
    del bpy.types.Scene.comfy_control_path
    del bpy.types.Scene.comfy_camera_slots
    del bpy.types.Scene.comfy_active_camera_slot
