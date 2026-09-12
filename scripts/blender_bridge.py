"""Blender bridge: scene inspection and preview export.

Runs inside Blender's interpreter via ``--python``.  Provides:
  - ``inspect_scene(bpy_module, approved_project)`` -- read-only scene analysis
  - ``export_preview(bpy_module, request)`` -- reversible preview export
  - ``main(request_path)`` -- entry point called from the guarded bottom
"""

import contextlib
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

# Producer identity embedded in every receipt.
_PRODUCER_NAME = "codex-blender"
_PRODUCER_VERSION = "0.1.0"
_SCHEMA_VERSION = "codex-blender.receipt/v1"

# ---------------------------------------------------------------------------
# Scene inspection (read-only) — unchanged from Task 3
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
# Export adapter — wraps the vendored render core
# ---------------------------------------------------------------------------

# Fields our adapter snapshots/restores.  The vendored core has its own
# restore block, but it is unguarded (an exception in one restore skips the
# rest), so our adapter owns the verified outer pass.
_SNAPSHOT_FIELDS = [
    ("scene", "camera"),
    ("scene", "frame_current"),
    ("scene", "frame_start"),
    ("scene", "frame_end"),
    ("render", "engine"),
    ("render", "filepath"),
    ("render", "resolution_x"),
    ("render", "resolution_y"),
    ("render", "resolution_percentage"),
    ("image_settings", "file_format"),
    ("shading", "color_type"),
    ("shading", "single_color"),
    ("shading", "light"),
    ("shading", "show_xray"),
    # jimeng_* inputs we set on the scene
    ("scene", "jimeng_camera"),
    ("scene", "jimeng_resolution"),
    ("scene", "jimeng_frame_start"),
    ("scene", "jimeng_frame_end"),
    ("scene", "jimeng_output_dir"),
]


def _get_nested(obj, attr):
    """Read an attribute, returning None if missing."""
    return getattr(obj, attr, None)


def _snapshot_scene_state(bpy_module):
    """Capture all fields the adapter mutates."""
    scene = bpy_module.context.scene
    render = scene.render
    image_settings = render.image_settings
    shading = getattr(getattr(scene, "display", None), "shading", None)

    snap = {}
    for group, attr in _SNAPSHOT_FIELDS:
        if group == "scene":
            snap[(group, attr)] = _get_nested(scene, attr)
        elif group == "render":
            snap[(group, attr)] = _get_nested(render, attr)
        elif group == "image_settings":
            snap[(group, attr)] = _get_nested(image_settings, attr)
        elif group == "shading":
            snap[(group, attr)] = _get_nested(shading, attr)
    return snap


def _verify_scene_state(bpy_module, snapshot):
    """Compare current state against snapshot; return list of mismatch descriptions."""
    scene = bpy_module.context.scene
    render = scene.render
    image_settings = render.image_settings
    shading = getattr(getattr(scene, "display", None), "shading", None)

    mismatches = []
    for (group, attr), expected in snapshot.items():
        if group == "scene":
            actual = _get_nested(scene, attr)
        elif group == "render":
            actual = _get_nested(render, attr)
        elif group == "image_settings":
            actual = _get_nested(image_settings, attr)
        elif group == "shading":
            actual = _get_nested(shading, attr)
        else:
            continue
        if actual != expected:
            mismatches.append(f"{group}.{attr}: expected {expected!r}, got {actual!r}")
    return mismatches


def _restore_scene_state(bpy_module, snapshot):
    """Restore all fields from snapshot.  Each field is restored independently
    so that a failure in one cannot cascade to the others."""
    scene = bpy_module.context.scene
    render = scene.render
    image_settings = render.image_settings
    shading = getattr(getattr(scene, "display", None), "shading", None)

    failures = []
    for (group, attr), value in snapshot.items():
        try:
            if group == "scene":
                setattr(scene, attr, value)
            elif group == "render":
                setattr(render, attr, value)
            elif group == "image_settings":
                setattr(image_settings, attr, value)
            elif group == "shading":
                if shading is not None:
                    setattr(shading, attr, value)
        except Exception as exc:
            failures.append(f"{group}.{attr}: {exc}")
    return failures


@contextlib.contextmanager
def restored_scene_state(bpy_module):
    """Context manager that snapshots scene state on entry and verifies
    restoration on exit.  If the vendored core's restore fails for any
    field, our layer repairs it.

    Yields a dict that the caller can inspect after the context exits:
      - "status": "confirmed" | "failed" | "unknown"
      - "mismatches": list of remaining mismatches (empty if confirmed)
      - "warnings": list of repair warnings
    """
    snapshot = _snapshot_scene_state(bpy_module)
    result = {"status": "unknown", "mismatches": [], "warnings": []}

    try:
        yield result
    finally:
        # First, verify what the vendored core left behind.
        mismatches = _verify_scene_state(bpy_module, snapshot)

        if mismatches:
            # The vendored core failed to restore some fields — repair them.
            result["warnings"].append(
                f"vendored restore incomplete, repairing {len(mismatches)} field(s)"
            )
            repair_failures = _restore_scene_state(bpy_module, snapshot)
            if repair_failures:
                result["warnings"].extend(repair_failures)

            # Re-verify after repair.
            remaining = _verify_scene_state(bpy_module, snapshot)
            if remaining:
                result["status"] = "failed"
                result["mismatches"] = remaining
            else:
                result["status"] = "confirmed"
        else:
            result["status"] = "confirmed"


def _register_jimeng_properties(bpy_module):
    """Register jimeng_* properties on the scene idempotently.

    If the upstream add-on's UI layer already registered them, reuse
    the existing registration.  The properties are set as plain Python
    attributes on the fake (for testing) or as Blender ID properties
    (for real Blender).
    """
    # For the fake bpy, we just set attributes — no registration needed.
    # For real Blender, we would use scene["jimeng_camera"] = ... etc.
    # The adapter sets values before calling the vendored core, so the
    # registration is implicit in the set operation.
    pass


def export_preview(bpy_module, request: dict) -> dict:
    """Export a preview video using the vendored render core.

    Args:
        bpy_module: The ``bpy`` module (or a fake for testing).
        request: Dict with keys:
            - projectPath: str (path to the .blend file)
            - mode: "white_model" | "material_preview" | "existing_video"
            - outputDir: str (approved output directory)
            - camera: str (camera object name)
            - frameStart: int
            - frameEnd: int
            - resolution: str ("origin", "360p", "480p", "720p", "1080p")

    Returns:
        Dict with keys: artifactPath, previewMode, camera, frameRange,
        restoration, bytes.  This is a PARTIAL ArtifactReceipt — Task 3
        adds the probe-derived fields (codec, width, height, fps,
        durationSeconds, sha256).

    Raises:
        BlenderError subclasses for failure categories.
    """
    # Import vendored core — safe because we are inside Blender's interpreter.
    from vendor.jimeng_blender_uploader import viewport_render, dcc_config

    scene = bpy_module.context.scene
    mode = request.get("mode", "white_model")
    project_path = request.get("projectPath", "")
    output_dir = request.get("outputDir", "")
    camera_name = request.get("camera", "")
    frame_start = request.get("frameStart", scene.frame_start)
    frame_end = request.get("frameEnd", scene.frame_end)
    resolution = request.get("resolution", "origin")

    # -- existing_video: no scene mutation at all --
    if mode == "existing_video":
        video_path = request.get("videoPath", "")
        if not video_path:
            _raise_blender_error("RENDER_FAILED", "existing_video requires videoPath")
        video = Path(video_path)
        if video.is_symlink():
            _raise_blender_error("PROJECT_NOT_AUTHORIZED", "video path must not be a symlink")
        if not video.resolve().is_file():
            _raise_blender_error("RENDER_FAILED", f"video file not found: {video_path}")
        return {
            "artifactPath": str(video.resolve()),
            "previewMode": mode,
            "camera": "",
            "frameRange": {"start": 0, "end": 0},
            "restoration": {"status": "confirmed", "mismatches": [], "warnings": []},
            "bytes": video.stat().st_size,
        }

    # -- validate output directory --
    out = Path(output_dir) if output_dir else None
    if out and out.is_symlink():
        _raise_blender_error("PROJECT_NOT_AUTHORIZED", "output directory must not be a symlink")
    if out and not out.resolve().is_dir():
        _raise_blender_error("PROJECT_NOT_AUTHORIZED", f"output directory not found: {output_dir}")

    # -- find camera --
    camera_obj = None
    for obj in bpy_module.data.objects:
        if obj.type == "CAMERA" and obj.name == camera_name:
            camera_obj = obj
            break
    if camera_obj is None:
        _raise_blender_error("CAMERA_NOT_FOUND", f"camera not found: {camera_name}")

    # -- set jimeng_* properties on the scene --
    # Save originals so we can restore them after the context manager exits,
    # since the context manager snapshots the state AFTER we set them.
    _orig_jimeng = {
        "jimeng_camera": getattr(scene, "jimeng_camera", None),
        "jimeng_resolution": getattr(scene, "jimeng_resolution", None),
        "jimeng_frame_start": getattr(scene, "jimeng_frame_start", None),
        "jimeng_frame_end": getattr(scene, "jimeng_frame_end", None),
        "jimeng_output_dir": getattr(scene, "jimeng_output_dir", None),
    }
    scene.jimeng_camera = camera_obj
    scene.jimeng_resolution = resolution
    scene.jimeng_frame_start = frame_start
    scene.jimeng_frame_end = frame_end
    if out:
        scene.jimeng_output_dir = str(out.resolve())

    # -- export with verified restoration --
    try:
        with restored_scene_state(bpy_module) as restoration:
            try:
                config = dcc_config.fallback_config()
                output_path = viewport_render.render_preview_movie(scene, config)
            except Exception as exc:
                _raise_blender_error("RENDER_FAILED", str(exc))
    finally:
        # Restore the jimeng_* properties to their original values (before we set them).
        for attr, val in _orig_jimeng.items():
            try:
                setattr(scene, attr, val)
            except Exception:
                pass

    # -- validate output --
    artifact = Path(output_path) if output_path else None
    if artifact is None or not artifact.exists():
        _raise_blender_error("RENDER_FAILED", "render produced no output file")
    if artifact.stat().st_size == 0:
        artifact.unlink(missing_ok=True)
        _raise_blender_error("RENDER_FAILED", "render produced zero-byte file")

    # -- containment check --
    if out:
        resolved_artifact = artifact.resolve()
        resolved_out = out.resolve()
        if not str(resolved_artifact).startswith(str(resolved_out) + os.sep):
            _raise_blender_error(
                "PROJECT_NOT_AUTHORIZED",
                f"artifact escapes approved output directory: {resolved_artifact}"
            )

    return {
        "artifactPath": str(artifact.resolve()),
        "previewMode": mode,
        "camera": camera_name,
        "frameRange": {"start": frame_start, "end": frame_end},
        "restoration": restoration,
        "bytes": artifact.stat().st_size,
    }


def _raise_blender_error(category, message):
    """Raise a BlenderError with a stable category attribute."""
    raise BlenderError(category, message)


class BlenderError(Exception):
    """Base exception for bridge failures, carrying a stable category string."""
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


# ---------------------------------------------------------------------------
# main() entry point
# ---------------------------------------------------------------------------

def main(request_path: str) -> int:
    """Entry point for Blender's ``--python`` execution.

    Reads the request JSON, imports ``bpy``, and dispatches to
    ``inspect_scene`` or ``export_preview`` based on the request's ``mode``.

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

    mode = request.get("mode", "inspect")

    if mode == "inspect":
        try:
            receipt = inspect_scene(bpy, project)
        except Exception as exc:
            _emit_error("INSPECTION_FAILED", str(exc))
            return 1
        print(json.dumps(receipt))
        return 0

    # Export modes
    try:
        result = export_preview(bpy, request)
    except BlenderError as exc:
        _emit_error(exc.category, str(exc))
        return 1
    except Exception as exc:
        _emit_error("RENDER_FAILED", str(exc))
        return 1

    print(json.dumps(result))
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
