import bpy
from bpy.props import StringProperty, CollectionProperty, IntProperty
from bpy.types import PropertyGroup
from .comfy_api import COMFY_URL_DEFAULT


class ComfyInput(PropertyGroup):
    """Stores one [CC] tagged input from the workflow"""
    node_id: StringProperty()
    input_key: StringProperty()
    label: StringProperty()
    value: StringProperty()


class ComfyImage(PropertyGroup):
    """Stores one generated image"""
    name: StringProperty()
    filepath: StringProperty(subtype="FILE_PATH")
    prompt_id: StringProperty()


def register():
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


def unregister():
    bpy.utils.unregister_class(ComfyInput)
    bpy.utils.unregister_class(ComfyImage)
    del bpy.types.Scene.comfy_server_url
    del bpy.types.Scene.comfy_workflow_path
    del bpy.types.Scene.comfy_output_dir
    del bpy.types.Scene.comfy_inputs
    del bpy.types.Scene.comfy_images
    del bpy.types.Scene.comfy_active_image
