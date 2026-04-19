import bpy
from bpy.props import StringProperty, CollectionProperty
from bpy.types import PropertyGroup
from .comfy_api import COMFY_URL_DEFAULT


class ComfyInput(PropertyGroup):
    """Stores one [CC] tagged input from the workflow"""
    node_id: StringProperty()
    input_key: StringProperty()
    label: StringProperty()
    value: StringProperty()


def register():
    bpy.utils.register_class(ComfyInput)
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
    bpy.utils.unregister_class(ComfyInput)
    del bpy.types.Scene.comfy_server_url
    del bpy.types.Scene.comfy_workflow_path
    del bpy.types.Scene.comfy_inputs
