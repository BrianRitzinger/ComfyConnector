import json
import os
import urllib.request
import urllib.error
import urllib.parse

CC_PREFIX = "[CC]"
COMFY_URL_DEFAULT = "http://localhost:8188"


def check_connection(server_url: str) -> str | None:
    """Returns None on success, error message on failure."""
    try:
        with urllib.request.urlopen(f"{server_url}/system_stats", timeout=3) as response:
            json.loads(response.read())
        return None
    except urllib.error.URLError as e:
        return str(e)


def submit_prompt(server_url: str, workflow: dict) -> tuple[str, str | None]:
    """Submit workflow to ComfyUI. Returns (prompt_id, error_message)."""
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{server_url}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read())
        return result.get("prompt_id", "unknown"), None
    except urllib.error.URLError as e:
        return "", str(e)


def interrupt(server_url: str) -> str | None:
    """Send interrupt to ComfyUI. Returns None on success, error message on failure."""
    try:
        req = urllib.request.Request(f"{server_url}/interrupt", data=b"", method="POST")
        urllib.request.urlopen(req, timeout=5)
        return None
    except urllib.error.URLError as e:
        return str(e)


def get_history(server_url: str, prompt_id: str) -> dict | None:
    """Returns output dict if generation is complete, None if still running."""
    try:
        with urllib.request.urlopen(f"{server_url}/history/{prompt_id}", timeout=5) as response:
            data = json.loads(response.read())
        entry = data.get(prompt_id, {})
        if entry.get("status", {}).get("completed"):
            return entry
        return None
    except urllib.error.URLError:
        return None


def download_image(server_url: str, img_info: dict, output_dir: str) -> str | None:
    """Download one image from ComfyUI and save to output_dir. Returns filepath or None."""
    params = urllib.parse.urlencode({
        "filename": img_info["filename"],
        "subfolder": img_info.get("subfolder", ""),
        "type": img_info.get("type", "output"),
    })
    try:
        with urllib.request.urlopen(f"{server_url}/view?{params}", timeout=30) as response:
            data = response.read()
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, img_info["filename"])
        with open(filepath, "wb") as f:
            f.write(data)
        return filepath
    except Exception:
        return None


def upload_image(server_url: str, filepath: str) -> tuple[str, str | None]:
    """Upload a local image to ComfyUI's input folder. Returns (server_filename, error)."""
    filename = os.path.basename(filepath)
    boundary = "----ComfyConnectorBoundary"

    with open(filepath, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n"
        f"\r\n"
    ).encode() + file_data + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="type"\r\n\r\ninput\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
        f"--{boundary}--\r\n"
    ).encode()

    req = urllib.request.Request(
        f"{server_url}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read())
        return result["name"], None
    except Exception as e:
        return "", str(e)


def scan_workflow_inputs(workflow: dict) -> list[dict]:
    """Return list of {node_id, input_key, label, value, class_type} for all [CC] tagged nodes."""
    inputs = []
    for node_id, node in workflow.items():
        title = node.get("_meta", {}).get("title", "")
        if CC_PREFIX not in title:
            continue
        label = title.replace(CC_PREFIX, "").strip()
        class_type = node.get("class_type", "")
        for key, value in node.get("inputs", {}).items():
            if isinstance(value, list):
                continue  # skip node-to-node links
            inputs.append({
                "node_id": node_id,
                "input_key": key,
                "label": f"{label} — {key}",
                "value": str(value),
                "class_type": class_type,
            })
    return inputs


def build_prompt(workflow_path: str, inputs, server_url: str = "") -> dict:
    """Load workflow JSON and patch in current [CC] input values.

    If server_url is provided, local file paths on LoadImage nodes are uploaded automatically.
    """
    with open(workflow_path, "r") as f:
        workflow = json.load(f)

    for item in inputs:
        node = workflow.get(item.node_id)
        if not node:
            continue

        # Auto-upload local files for LoadImage nodes
        if server_url and node.get("class_type") == "LoadImage" and os.path.isfile(item.value):
            server_name, error = upload_image(server_url, item.value)
            if not error:
                node["inputs"][item.input_key] = server_name
                continue

        original = node["inputs"].get(item.input_key)
        # bool must be checked before int — bool is a subclass of int in Python
        if isinstance(original, bool):
            node["inputs"][item.input_key] = item.value.lower() == "true"
        elif isinstance(original, int):
            node["inputs"][item.input_key] = int(item.value)
        elif isinstance(original, float):
            node["inputs"][item.input_key] = float(item.value)
        else:
            node["inputs"][item.input_key] = item.value

    return workflow
