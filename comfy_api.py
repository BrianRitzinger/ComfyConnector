import json
import urllib.request
import urllib.error

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


def scan_workflow_inputs(workflow: dict) -> list[dict]:
    """Return list of {node_id, input_key, label, value} for all [CC] tagged nodes."""
    inputs = []
    for node_id, node in workflow.items():
        title = node.get("_meta", {}).get("title", "")
        if CC_PREFIX not in title:
            continue
        label = title.replace(CC_PREFIX, "").strip()
        for key, value in node.get("inputs", {}).items():
            if isinstance(value, list):
                continue  # skip node-to-node links
            inputs.append({
                "node_id": node_id,
                "input_key": key,
                "label": f"{label} — {key}",
                "value": str(value),
            })
    return inputs


def build_prompt(workflow_path: str, inputs) -> dict:
    """Load workflow JSON and patch in current [CC] input values."""
    with open(workflow_path, "r") as f:
        workflow = json.load(f)

    for item in inputs:
        node = workflow.get(item.node_id)
        if not node:
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
