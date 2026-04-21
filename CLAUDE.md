# ComfyConnector — Claude Code Notes

## What this is
Blender 5.1+ addon connecting Blender to ComfyUI's REST API. Renders Blender control images (normal maps, full renders), uploads them to ComfyUI, submits workflows, and pulls generated images back into Blender.

## Module layout
| File | Purpose |
|------|---------|
| `__init__.py` | Thin registry — imports modules, delegates register/unregister |
| `blender_manifest.toml` | Blender 5.x extension metadata (replaces legacy bl_info) |
| `comfy_api.py` | All HTTP — no bpy imports. upload, submit, poll, download |
| `properties.py` | PropertyGroups and Scene properties |
| `operators.py` | All bpy.types.Operator classes + timer polling |
| `panels.py` | UI panel and UIList |
| `previews.py` | bpy.utils.previews thumbnail cache |

## [CC] tag convention
In ComfyUI, rename any node's title to start with `[CC]` to expose its inputs as editable fields in the Blender panel. Example: `[CC] Prompt` exposes the text input. `[CC] Control Image` on a LoadImage node triggers auto-upload of the rendered control image on workflow submit.

## Key behaviors
- `scan_workflow_inputs` reads `_meta.title` for `[CC]` prefix, skips list values (node-to-node links)
- `build_prompt` patches [CC] inputs back into workflow JSON preserving original types (bool/int/float/str). For LoadImage nodes with a local file path, it calls `upload_image` first.
- Polling uses `bpy.app.timers` — non-blocking, 2s interval
- Normal map render: temporary emission material (ShaderNodeNewGeometry → world normals → 0-1 range), overrides all mesh materials, renders, restores

## Development setup
Symlink for live editing (no reinstall per change):
```
ln -s ~/Projects/ComfyConnector ~/.config/blender/5.1/extensions/user_default/comfy_connector
```
Reload addon in Blender: Edit → Preferences → Add-ons → ComfyConnector → disable/enable.
Launch Blender from terminal to see print/error output.

## Gotchas
- `bool` is a subclass of `int` in Python — always check `isinstance(x, bool)` before `isinstance(x, int)`
- Camera background images live on `camera.data`, not the viewport `space_data`
- Blender 5.x Workbench has no `NORMAL` color type — use emission material override instead
- `bpy.app.timers` callback must return `None` to stop or a float (seconds) to reschedule
