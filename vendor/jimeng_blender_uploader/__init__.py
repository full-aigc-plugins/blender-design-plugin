"""Blender add-on for exporting preview videos to Jimeng/Dreamina."""

from __future__ import annotations

bl_info = {
    "name": '即梦 Seedance 2.5 预览渲染上传器',
    "author": "Codex",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Jimeng",
    "description": "Render or choose a preview video and import it into Jimeng/Dreamina Web.",
    "category": "Import-Export",
}

import importlib
import json

import bpy
from bpy.app.handlers import persistent

from . import dcc_config, operators, panel, settings, state, upload_bridge, variant, viewport_render

dcc_config = importlib.reload(dcc_config)
variant = importlib.reload(variant)
settings = importlib.reload(settings)
upload_bridge = importlib.reload(upload_bridge)
viewport_render = importlib.reload(viewport_render)
state = importlib.reload(state)
operators = importlib.reload(operators)
panel = importlib.reload(panel)

_FRAME_RANGE_UPDATING = False
_EXPORT_SYNC_INTERVAL_SECONDS = 3.0


def _initialize_scene(scene):
    if scene is None:
        return
    operators.initialize_scene_defaults(scene)


def _safe_initialize_scene(scene):
    try:
        _initialize_scene(scene)
    except Exception:
        pass


def _safe_update_dcc_protocol_properties(scene):
    if scene is None:
        return
    try:
        operators.update_dcc_protocol_properties(scene)
    except Exception:
        pass


@persistent
def _initialize_after_file_load(_dummy):
    scene = getattr(bpy.context, "scene", None)
    _safe_initialize_scene(scene)
    _safe_update_dcc_protocol_properties(scene)


def _camera_poll(_self, obj):
    return obj is not None and obj.type == "CAMERA"


def _camera_key(camera):
    if camera is None:
        return ""
    return getattr(camera, "name_full", None) or getattr(camera, "name", "")


def _camera_cache(scene):
    try:
        data = json.loads(getattr(scene, "jimeng_camera_cache_json", "") or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_camera_cache(scene, cache):
    try:
        scene.jimeng_camera_cache_json = json.dumps(cache, ensure_ascii=False)
    except Exception:
        scene.jimeng_camera_cache_json = "{}"


def _invalidate_link(scene, _context=None):
    if getattr(scene, "jimeng_task_state", "IDLE") == "RUNNING":
        return
    state.clear_link(scene, reset_task=True)


def load_camera_cache(scene, camera):
    key = _camera_key(camera)
    scene.jimeng_active_camera_key = key
    if not key:
        scene.jimeng_prompt = ""
        scene.jimeng_redirect_url = ""
        scene.jimeng_redirect_url_display = ""
        scene.jimeng_link_ready = False
        state.clear_link(scene, reset_task=True)
        return

    cached = _camera_cache(scene).get(key)
    if isinstance(cached, dict):
        scene.jimeng_redirect_url = cached.get("redirect_url", "") or ""
        scene.jimeng_redirect_url_display = scene.jimeng_redirect_url
        scene.jimeng_link_ready = bool(scene.jimeng_redirect_url)
        state.clear_link(scene, reset_task=True)
        return

    scene.jimeng_redirect_url = ""
    scene.jimeng_redirect_url_display = ""
    scene.jimeng_link_ready = False
    state.clear_link(scene, reset_task=True)


def _camera_update(scene, _context):
    scene.jimeng_active_camera_key = _camera_key(getattr(scene, "jimeng_camera", None))
    try:
        scene.jimeng_frame_range_manual = False
        operators.sync_selected_camera_export_parameters(scene, sync_frame_range=True)
    except Exception:
        pass
    _invalidate_link(scene)


def _redirect_display_update(scene, _context):
    actual = getattr(scene, "jimeng_redirect_url", "")
    if getattr(scene, "jimeng_redirect_url_display", "") != actual:
        scene.jimeng_redirect_url_display = actual


def _frame_limit_display_get(scene):
    try:
        return operators.frame_limit_label(scene)
    except Exception:
        return str(dcc_config.DEFAULT_DURATION * dcc_config.DEFAULT_FPS)


def _frame_range_update(scene, _context):
    global _FRAME_RANGE_UPDATING
    if _FRAME_RANGE_UPDATING:
        return
    if not operators.frame_range_syncing():
        scene.jimeng_frame_range_manual = True
    try:
        _FRAME_RANGE_UPDATING = True
        operators.clamp_frame_range(scene)
    except Exception:
        pass
    finally:
        _FRAME_RANGE_UPDATING = False
    _invalidate_link(scene)


def _sync_export_parameters_timer():
    scene = getattr(bpy.context, "scene", None)
    if not scene:
        return _EXPORT_SYNC_INTERVAL_SECONDS
    if not hasattr(scene, "jimeng_uploader_mode"):
        return _EXPORT_SYNC_INTERVAL_SECONDS
    if getattr(scene, "jimeng_uploader_mode", "VIEWPORT") != "VIEWPORT":
        return _EXPORT_SYNC_INTERVAL_SECONDS
    if getattr(scene, "jimeng_task_state", "IDLE") == "RUNNING":
        return _EXPORT_SYNC_INTERVAL_SECONDS

    try:
        before = state.input_signature(scene)
        operators.sync_selected_camera_export_parameters(scene)
        after = state.input_signature(scene)
        if before != after or (
            getattr(scene, "jimeng_link_signature", "") and not state.link_is_current(scene)
        ):
            _invalidate_link(scene)
    except Exception:
        pass
    return _EXPORT_SYNC_INTERVAL_SECONDS


def _register_timer(callback, first_interval, persistent=False):
    try:
        if bpy.app.timers.is_registered(callback):
            return
    except Exception:
        pass
    bpy.app.timers.register(
        callback,
        first_interval=first_interval,
        persistent=persistent,
    )


def _unregister_timer(callback):
    try:
        if bpy.app.timers.is_registered(callback):
            bpy.app.timers.unregister(callback)
    except Exception:
        pass


def register():
    bpy.types.Scene.jimeng_uploader_mode = bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("VIEWPORT", "相机渲染", "用当前 Blender Camera 导出预览视频并生成链接"),
            ("EXISTING", "本地上传", "选择已有预览视频并生成链接"),
        ),
        default="VIEWPORT",
        update=_invalidate_link,
    )
    bpy.types.Scene.jimeng_video_path = bpy.props.StringProperty(
        name="Video",
        subtype="FILE_PATH",
        description="Existing preview video to upload",
        default="",
        update=_invalidate_link,
    )
    bpy.types.Scene.jimeng_output_dir = bpy.props.StringProperty(
        name="Output Dir",
        subtype="DIR_PATH",
        description="Directory for generated preview videos",
        default="",
        update=_invalidate_link,
    )
    bpy.types.Scene.jimeng_camera = bpy.props.PointerProperty(
        name="Camera",
        type=bpy.types.Object,
        poll=_camera_poll,
        description="Camera used for viewport render",
        update=_camera_update,
    )
    bpy.types.Scene.jimeng_resolution = bpy.props.EnumProperty(
        name="Resolution",
        items=(
            ("360p", "360P", "Use Origin aspect ratio with a 360px short edge"),
            ("480p", "480P", "Use Origin aspect ratio with a 480px short edge"),
            ("720p", "720P", "Use Origin aspect ratio with a 720px short edge"),
            ("1080p", "1080P", "Use Origin aspect ratio with a 1080px short edge"),
            ("origin", "Origin", "Use the live Output resolution and percentage"),
        ),
        default=dcc_config.DEFAULT_RESOLUTION_KEY,
        options={"SKIP_SAVE"},
        update=_invalidate_link,
    )
    bpy.types.Scene.jimeng_frame_start = bpy.props.IntProperty(
        name="start",
        description="",
        default=1,
        min=-100000,
        max=100000,
        options={"SKIP_SAVE"},
        update=_frame_range_update,
    )
    bpy.types.Scene.jimeng_frame_end = bpy.props.IntProperty(
        name="end",
        description="",
        default=120,
        min=-100000,
        max=100000,
        options={"SKIP_SAVE"},
        update=_frame_range_update,
    )
    bpy.types.Scene.jimeng_frame_range_initialized = bpy.props.BoolProperty(
        name="Jimeng Frame Range Initialized",
        default=False,
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_frame_range_manual = bpy.props.BoolProperty(
        name="Jimeng Frame Range Manual",
        default=False,
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_default_params_expanded = bpy.props.BoolProperty(
        name="默认参数",
        description="Show default protocol parameters",
        default=True,
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_prompt = bpy.props.StringProperty(
        name="Prompt",
        description="Prompt filled into Jimeng/Dreamina after upload",
        default="",
        maxlen=4096,
    )
    bpy.types.Scene.jimeng_redirect_url = bpy.props.StringProperty(
        name="Jimeng Link",
        default="",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_redirect_url_display = bpy.props.StringProperty(
        name="",
        description="",
        default="",
        options={"SKIP_SAVE"},
        update=_redirect_display_update,
    )
    bpy.types.Scene.jimeng_link_ready = bpy.props.BoolProperty(
        name="Jimeng Link Ready",
        default=False,
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_link_signature = bpy.props.StringProperty(
        name="Jimeng Link Signature",
        default="",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_camera_cache_json = bpy.props.StringProperty(
        name="Jimeng Camera Cache",
        default="{}",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_active_camera_key = bpy.props.StringProperty(
        name="Jimeng Active Camera Key",
        default="",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_status = bpy.props.StringProperty(
        name="Status",
        default="Ready.",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_status_detail = bpy.props.StringProperty(
        name="Status Detail",
        default="",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_task_state = bpy.props.EnumProperty(
        name="Task State",
        items=(
            ("IDLE", "Idle", ""),
            ("RUNNING", "Running", ""),
            ("SUCCESS", "Success", ""),
            ("FAILED", "Failed", ""),
        ),
        default="IDLE",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_task_message = bpy.props.StringProperty(
        name="Task Message",
        default="",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_error_message = bpy.props.StringProperty(
        name="Error Message",
        default="",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_dcc_fps = bpy.props.IntProperty(
        name="DCC FPS",
        default=dcc_config.DEFAULT_FPS,
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_dcc_container_format = bpy.props.StringProperty(
        name="DCC Container",
        default=dcc_config.DEFAULT_CONTAINER_FORMAT,
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_dcc_codec = bpy.props.StringProperty(
        name="DCC Codec",
        default=dcc_config.DEFAULT_CODEC,
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_dcc_file_size_label = bpy.props.StringProperty(
        name="DCC File Size",
        default="200M",
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_dcc_min_frame_num = bpy.props.IntProperty(
        name="DCC Min Frame Count",
        default=dcc_config.DEFAULT_MIN_FRAME_NUM,
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_dcc_max_frame_num = bpy.props.IntProperty(
        name="DCC Max Frame Count",
        default=dcc_config.DEFAULT_DURATION * dcc_config.DEFAULT_FPS,
        options={"SKIP_SAVE"},
    )
    bpy.types.Scene.jimeng_frame_limit_display = bpy.props.StringProperty(
        name="Frame Limit",
        get=_frame_limit_display_get,
        options={"SKIP_SAVE"},
    )
    operators.register()
    panel.register()
    if _initialize_after_file_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_initialize_after_file_load)
    scene = getattr(bpy.context, "scene", None)
    _safe_initialize_scene(scene)
    _safe_update_dcc_protocol_properties(scene)
    _register_timer(
        _sync_export_parameters_timer,
        first_interval=_EXPORT_SYNC_INTERVAL_SECONDS,
        persistent=True,
    )


def unregister():
    _unregister_timer(_sync_export_parameters_timer)
    if _initialize_after_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_initialize_after_file_load)
    panel.unregister()
    operators.unregister()

    for name in (
        "jimeng_uploader_mode",
        "jimeng_video_path",
        "jimeng_output_dir",
        "jimeng_camera",
        "jimeng_resolution",
        "jimeng_frame_start",
        "jimeng_frame_end",
        "jimeng_frame_range_initialized",
        "jimeng_frame_range_manual",
        "jimeng_default_params_expanded",
        "jimeng_prompt",
        "jimeng_redirect_url",
        "jimeng_redirect_url_display",
        "jimeng_link_ready",
        "jimeng_link_signature",
        "jimeng_camera_cache_json",
        "jimeng_active_camera_key",
        "jimeng_status",
        "jimeng_status_detail",
        "jimeng_task_state",
        "jimeng_task_message",
        "jimeng_error_message",
        "jimeng_dcc_fps",
        "jimeng_dcc_container_format",
        "jimeng_dcc_codec",
        "jimeng_dcc_file_size_label",
        "jimeng_dcc_min_frame_num",
        "jimeng_dcc_max_frame_num",
        "jimeng_frame_limit_display",
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
