"""Headless Codex driver over the vendored `jimeng_blender_uploader` add-on.

This module is deliberately thin. It does NOT reimplement any add-on behaviour:
it enables the vendored add-on, sets the same scene inputs the Blender panel
would set, invokes the add-on's own operator for the requested flow, and reads
back the state the operator produced.

Camera render flow  -> JIMENG_OT_render_upload     (bpy.ops.jimeng.render_upload)
Local upload flow   -> JIMENG_OT_upload_existing   (bpy.ops.jimeng.upload_existing)

Everything else — protocol fetch/validation, frame-range derivation/validation,
rendering, file-size validation, link production, the error taxonomy — belongs to
the vendored add-on. See vendor/jimeng_blender_uploader/UPSTREAM.md.
"""

import sys
from pathlib import Path

# Flow names used in the request, and the vendored mode each maps to.
FLOW_CAMERA_RENDER = "camera_render"
FLOW_LOCAL_UPLOAD = "local_upload"

_MODE_FOR_FLOW = {
    FLOW_CAMERA_RENDER: "VIEWPORT",
    FLOW_LOCAL_UPLOAD: "EXISTING",
}

# Scene-state fields the add-on populates and we project into a result.
_RESULT_FIELDS = (
    "jimeng_task_state",
    "jimeng_task_message",
    "jimeng_error_message",
    "jimeng_redirect_url",
    "jimeng_video_path",
    "jimeng_status",
    "jimeng_status_detail",
    "jimeng_link_ready",
)


def enable_addon(bpy_module):
    """Enable the vendored add-on inside Blender.

    Calls the upstream ``register()``, which is the only place the scene
    properties, the operator classes, and the panel class are registered.
    Idempotent: re-registering already-registered classes raises in Blender,
    so we treat "already enabled" as success.
    """
    from vendor.jimeng_blender_uploader import register

    try:
        register()
    except ValueError as exc:
        # Blender raises when a class/property is already registered.
        if "already registered" not in str(exc):
            raise
    return True


def disable_addon(bpy_module):
    """Disable the vendored add-on (used by tests and teardown)."""
    from vendor.jimeng_blender_uploader import unregister

    try:
        unregister()
    except Exception:
        pass


def _require(bpy_module, name):
    module = getattr(bpy_module, name, None)
    if module is None:
        raise RuntimeError(f"bpy.{name} is unavailable")
    return module


def _validate_output_dir(output_dir):
    """Validate the approved output directory before handing it to the add-on.

    This is request validation, not a reimplementation of any add-on rule: the
    add-on writes wherever ``scene.jimeng_output_dir`` points and does not
    perform containment checks, so the scope check belongs to the caller.
    """
    path = Path(output_dir)
    if path.is_symlink():
        raise ValueError("outputDir must not be a symlink")
    resolved = path.resolve()
    if not resolved.is_dir():
        raise ValueError(f"outputDir is not an existing directory: {output_dir}")
    return str(resolved)


def _set_scene_inputs(bpy_module, scene, request, flow):
    """Set the scene properties the panel would set for this flow.

    These are exactly the inputs the add-on's operators read; no add-on rule is
    duplicated here — the operators own protocol, frame-range, and size
    validation.
    """
    scene.jimeng_uploader_mode = _MODE_FOR_FLOW[flow]

    prompt = request.get("prompt")
    if prompt is not None:
        scene.jimeng_prompt = prompt

    if flow == FLOW_LOCAL_UPLOAD:
        video_path = request.get("videoPath")
        if not video_path:
            raise ValueError("local_upload requires videoPath")
        scene.jimeng_video_path = str(video_path)
        return

    camera_name = request.get("camera")
    if camera_name:
        scene.jimeng_camera = _find_camera(bpy_module, camera_name)

    output_dir = request.get("outputDir")
    if output_dir:
        scene.jimeng_output_dir = _validate_output_dir(output_dir)

    for attr, key in (
        ("jimeng_resolution", "resolution"),
        ("jimeng_frame_start", "frameStart"),
        ("jimeng_frame_end", "frameEnd"),
    ):
        value = request.get(key)
        if value is not None and value != "":
            setattr(scene, attr, value)


def _find_camera(bpy_module, camera_name):
    """Return the camera object with this name, or raise the add-on's condition."""
    for obj in bpy_module.data.objects:
        if getattr(obj, "type", None) == "CAMERA" and getattr(obj, "name", None) == camera_name:
            return obj
    raise ValueError(f"no camera named {camera_name!r} in the scene")


def _project_result(bpy_module, scene, operator_result):
    """Project upstream scene state into the result Codex consumes.

    We report what the add-on decided; we do not reinterpret it.
    result["status"] is the add-on's own task state, and result["link"] is the
    link the add-on produced.
    """
    # Blender operators return a set literal, e.g. {"FINISHED"} or {"CANCELLED"}.
    if isinstance(operator_result, (set, frozenset)):
        normalized = sorted(operator_result)
        operator_result = normalized[0] if len(normalized) == 1 else normalized

    projected = {"operatorResult": operator_result}
    for field in _RESULT_FIELDS:
        projected[field] = getattr(scene, field, None)
    return projected


def run_flow(bpy_module, request):
    """Run one of the two add-on flows headlessly.

    Args:
        bpy_module: the ``bpy`` module (or a fake for testing).
        request: dict with:
            - flow: "camera_render" | "local_upload"
            - videoPath: str (local_upload only)
            - camera, resolution, frameStart, frameEnd, outputDir (camera_render)
            - prompt: optional str

    Returns:
        The projected result dict (see ``_project_result``).

    Raises:
        ValueError: for a malformed request (unknown flow, missing videoPath,
            named camera absent). These are request errors, not add-on errors.
    """
    flow = request.get("flow")
    if flow not in _MODE_FOR_FLOW:
        raise ValueError(
            f"unknown flow {flow!r}; expected one of {sorted(_MODE_FOR_FLOW)}"
        )

    enable_addon(bpy_module)

    scene = bpy_module.context.scene
    _set_scene_inputs(bpy_module, scene, request, flow)

    operators = _require(bpy_module, "ops").jimeng
    if flow == FLOW_CAMERA_RENDER:
        operator_result = operators.render_upload()
    else:
        operator_result = operators.upload_existing()

    return _project_result(bpy_module, scene, operator_result)
