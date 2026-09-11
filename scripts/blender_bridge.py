"""Blender bridge: read-only scene inspection and (future) preview export.

Runs inside Blender's interpreter via ``--python``.  Provides:
  - ``inspect_scene(bpy_module, approved_project)`` -- read-only scene analysis
  - ``main(request_path)`` -- entry point called from the guarded bottom

Task 4 will extend this file with preview export; keep inspection behind
its own entry point so the file stays cohesive.
"""

import hashlib
import json
import sys
from pathlib import Path

# Producer identity embedded in every receipt.
_PRODUCER_NAME = "codex-blender"
_PRODUCER_VERSION = "0.1.0"
_SCHEMA_VERSION = "codex-blender.receipt/v1"

# ---------------------------------------------------------------------------
# Scene inspection (read-only)
# ---------------------------------------------------------------------------

def inspect_scene(bpy_module, approved_project: Path) -> dict:
    """Inspect the loaded Blender scene and return a SceneReceipt dict.

    This function is read-only: it must not mutate selection, mode,
    active objects, or any datablock.

    Args:
        bpy_module: The ``bpy`` module (or a fake for testing).
        approved_project: Path to the .blend file for fingerprinting.

    Returns:
        A dict conforming to ``schemas/scene_receipt.schema.json``.
    """
    scene = bpy_module.context.scene

    # -- cameras --
    cameras = []
    for obj in bpy_module.data.objects:
        if obj.type == "CAMERA":
            cameras.append(obj.name)
    cameras.sort()  # deterministic order

    # -- warnings --
    warnings = []
    if not cameras:
        warnings.append("NO_CAMERAS")

    # -- frame range --
    frame_start = scene.frame_start
    frame_end = scene.frame_end
    if frame_start > frame_end or frame_start < 1:
        warnings.append("INVALID_FRAME_RANGE")

    # -- resolution (apply percentage scaling) --
    render = scene.render
    pct = render.resolution_percentage / 100.0
    width = int(render.resolution_x * pct)
    height = int(render.resolution_y * pct)

    # -- materials & preview modes --
    has_shader_nodes = False
    has_image_textures = False
    has_unsupported_nodes = False

    for mat in bpy_module.data.materials:
        if not mat.use_nodes or mat.node_tree is None:
            continue
        for node in mat.node_tree.nodes:
            if node.type == "SHADER":
                has_shader_nodes = True
            elif node.type == "TEX_IMAGE":
                has_image_textures = True
                has_shader_nodes = True
            else:
                has_unsupported_nodes = True

    preview_modes = ["white_model"]
    if has_shader_nodes:
        preview_modes.append("material_preview")
    if has_image_textures:
        preview_modes.append("textured")

    if has_unsupported_nodes:
        warnings.append("UNSUPPORTED_NODES")

    # -- linked assets --
    for obj in bpy_module.data.objects:
        if getattr(obj, "library", None) is not None:
            warnings.append("LINKED_ASSETS_OUTSIDE_SCOPE")
            break  # one warning is enough

    # -- project fingerprint (deterministic, from file content) --
    content = approved_project.read_bytes()
    fingerprint = hashlib.sha256(content).hexdigest()

    # -- blender version --
    blender_version = bpy_module.app.version_string

    # -- build receipt in schema field order --
    receipt = {
        "schemaVersion": _SCHEMA_VERSION,
        "producer": {"name": _PRODUCER_NAME, "version": _PRODUCER_VERSION},
        "blenderVersion": blender_version,
        "projectFingerprint": fingerprint,
        "cameras": cameras,
        "frameRange": {"start": frame_start, "end": frame_end},
        "resolution": {"width": width, "height": height},
        "previewModes": preview_modes,
        "warnings": sorted(warnings),
    }

    return receipt


# ---------------------------------------------------------------------------
# main() entry point
# ---------------------------------------------------------------------------

def main(request_path: str) -> int:
    """Entry point for Blender's ``--python`` execution.

    Reads the request JSON, imports ``bpy``, calls ``inspect_scene``,
    and emits exactly one JSON receipt to stdout.  Diagnostics go to stderr.

    Returns:
        0 on success, 1 on error.
    """
    # Import bpy here so tests can mock sys.modules["bpy"].
    import bpy

    # Read request
    try:
        with open(request_path) as f:
            request = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        _emit_error("INVALID_REQUEST", str(exc))
        return 1

    project_path = request.get("projectPath")
    if not project_path:
        _emit_error("INVALID_REQUEST", "missing projectPath")
        return 1

    project = Path(project_path)
    if project.is_symlink():
        _emit_error("PROJECT_NOT_AUTHORIZED", "project path must not be a symlink")
        return 1
    if not project.resolve().is_file():
        _emit_error("PROJECT_NOT_AUTHORIZED", "project file not found")
        return 1

    try:
        receipt = inspect_scene(bpy, project)
    except Exception as exc:
        _emit_error("INSPECTION_FAILED", str(exc))
        return 1

    # Emit exactly one JSON document to stdout.
    print(json.dumps(receipt))
    return 0


def _emit_error(category: str, message: str) -> None:
    """Write a JSON error object to stderr."""
    print(json.dumps({"category": category, "message": message}), file=sys.stderr)


# ---------------------------------------------------------------------------
# Guarded entry point for Blender's --python execution.
# Does NOT run on import.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        _sep = sys.argv.index("--")
        _request = sys.argv[_sep + 1]
    except (ValueError, IndexError):
        _emit_error("INVALID_REQUEST", "missing request path after -- separator")
        sys.exit(1)
    sys.exit(main(_request))
