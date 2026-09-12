"""Blender operators for the Jimeng/Dreamina uploader add-on."""

from __future__ import annotations

import os
import traceback
import webbrowser

import bpy

from . import dcc_config, settings, state, upload_bridge, variant, viewport_render


_FRAME_RANGE_SYNC_DEPTH = 0


def frame_range_syncing():
    return _FRAME_RANGE_SYNC_DEPTH > 0


def _set_frame_range_from_source(scene, start, end, initialized=True):
    global _FRAME_RANGE_SYNC_DEPTH
    _FRAME_RANGE_SYNC_DEPTH += 1
    try:
        if int(getattr(scene, "jimeng_frame_start", 0) or 0) != int(start):
            scene.jimeng_frame_start = int(start)
        if int(getattr(scene, "jimeng_frame_end", 0) or 0) != int(end):
            scene.jimeng_frame_end = int(end)
        if initialized and not getattr(scene, "jimeng_frame_range_initialized", False):
            scene.jimeng_frame_range_initialized = True
    finally:
        _FRAME_RANGE_SYNC_DEPTH -= 1


def _append_status(scene, stage, state, message):
    line = "[{0}] {1}: {2}".format(stage, state, message)
    scene.jimeng_status = line
    detail = getattr(scene, "jimeng_status_detail", "")
    lines = [item for item in detail.splitlines() if item.strip()]
    lines.append(line)
    scene.jimeng_status_detail = "\n".join(lines[-8:])
    return line


def _set_task(scene, task_state, message="", error=""):
    state.set_task(scene, task_state, message, error)


def _clear_run_status(scene):
    scene.jimeng_status = "Ready."
    scene.jimeng_status_detail = ""
    _set_task(scene, "IDLE", "", "")


def _friendly_error(scene, exc, stage):
    message = str(exc).strip()
    if "shorter than DCC min_frame_num" in message:
        return variant.text(
            "min_frames_hint",
            count=min_frame_limit(scene),
            seconds=dcc_config.DEFAULT_MIN_DURATION_SECONDS,
        )
    if "Frame range exceeds selected camera max frames" in message:
        return variant.text("error_frame_range", count=effective_frame_limit(scene))
    if isinstance(exc, dcc_config.DccConfigError):
        if "Exported file is too large" in message:
            return variant.text("error_file_size", size=scene.jimeng_dcc_file_size_label)
        if "shorter than DCC min_frame_num" in message:
            return variant.text(
                "min_frames_hint",
                count=min_frame_limit(scene),
                seconds=dcc_config.DEFAULT_MIN_DURATION_SECONDS,
            )
        if "Frame range exceeds" in message:
            return variant.text("error_frame_range", count=effective_frame_limit(scene))
        return variant.text("error_existing", reason=message)

    if stage == "config":
        return variant.text("error_config", reason=message)
    elif stage == "bridge":
        return variant.text("error_bridge", reason=message)
    elif stage == "existing":
        return variant.text("error_existing", reason=message)
    return variant.text("error_render", reason=message)


def _camera_key(scene):
    camera = getattr(scene, "jimeng_camera", None)
    if not camera:
        return ""
    return getattr(camera, "name_full", None) or getattr(camera, "name", "")


def _camera_cache(scene):
    try:
        import json

        data = json.loads(getattr(scene, "jimeng_camera_cache_json", "") or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _store_camera_cache(scene):
    key = _camera_key(scene)
    if not key:
        return
    import json

    cache = _camera_cache(scene)
    cache[key] = {
        "redirect_url": scene.jimeng_redirect_url,
    }
    scene.jimeng_camera_cache_json = json.dumps(cache, ensure_ascii=False)


def _compact_file_size(size):
    try:
        value = int(size)
    except Exception:
        value = dcc_config.DEFAULT_FILE_SIZE
    if value > 0 and value % (1024 * 1024) == 0:
        if getattr(variant, "LANGUAGE", "") == "en_us":
            return "{0} MB".format(value // (1024 * 1024))
        return "{0}M".format(value // (1024 * 1024))
    return dcc_config.format_bytes(value)


def update_dcc_protocol_properties(scene, config=None):
    config = config or dcc_config.fetch_dcc_protocol_config(settings.DEFAULT_TARGET_URL)
    protocol = dcc_config.video_protocol(config)
    scene.jimeng_dcc_fps = int(protocol.get("fps") or dcc_config.DEFAULT_FPS)
    scene.jimeng_dcc_container_format = str(
        protocol.get("container_format") or dcc_config.DEFAULT_CONTAINER_FORMAT
    )
    scene.jimeng_dcc_codec = str(protocol.get("codec") or dcc_config.DEFAULT_CODEC)
    scene.jimeng_dcc_file_size_label = _compact_file_size(
        protocol.get("file_size") or dcc_config.DEFAULT_FILE_SIZE
    )
    scene.jimeng_dcc_min_frame_num = int(
        protocol.get("min_frame_num") or dcc_config.DEFAULT_MIN_FRAME_NUM
    )
    scene.jimeng_dcc_max_frame_num = int(
        protocol.get("max_frame_num") or dcc_config.DEFAULT_DURATION * dcc_config.DEFAULT_FPS
    )
    try:
        clamp_frame_range(scene)
    except Exception:
        pass
    return config


def ensure_frame_range_properties(scene):
    if not getattr(scene, "jimeng_frame_range_initialized", False):
        _set_frame_range_from_source(scene, int(scene.frame_start), int(scene.frame_end))


def initialize_scene_defaults(scene):
    scene.jimeng_resolution = dcc_config.DEFAULT_RESOLUTION_KEY
    scene.jimeng_frame_range_manual = False
    scene.jimeng_frame_range_initialized = False
    sync_selected_camera_export_parameters(scene, sync_frame_range=True)


_CUSTOM_RENDER_WIDTH_KEYS = (
    "render_resolution_x",
    "renderResolutionX",
    "export_resolution_x",
    "exportResolutionX",
    "resolution_x",
    "resolutionX",
    "render_width",
    "renderWidth",
    "export_width",
    "exportWidth",
    "output_width",
    "outputWidth",
    "width",
)
_CUSTOM_RENDER_HEIGHT_KEYS = (
    "render_resolution_y",
    "renderResolutionY",
    "export_resolution_y",
    "exportResolutionY",
    "resolution_y",
    "resolutionY",
    "render_height",
    "renderHeight",
    "export_height",
    "exportHeight",
    "output_height",
    "outputHeight",
    "height",
)
_CUSTOM_RENDER_PERCENTAGE_KEYS = (
    "render_resolution_percentage",
    "renderResolutionPercentage",
    "export_resolution_percentage",
    "exportResolutionPercentage",
    "resolution_percentage",
    "resolutionPercentage",
    "resolution_percent",
    "resolutionPercent",
    "render_percent",
    "renderPercent",
    "export_percent",
    "exportPercent",
    "percentage",
    "percent",
)
_CUSTOM_RENDER_SIZE_KEYS = (
    "render_resolution",
    "renderResolution",
    "export_resolution",
    "exportResolution",
    "output_resolution",
    "outputResolution",
    "render_size",
    "renderSize",
    "export_size",
    "exportSize",
    "size",
    "resolution",
)
_CUSTOM_RENDER_GROUP_KEYS = (
    "render",
    "render_settings",
    "renderSettings",
    "export",
    "export_settings",
    "exportSettings",
    "output",
    "output_settings",
    "outputSettings",
)


def _coerce_number(value):
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _mapping_export_number(mapping, keys):
    if mapping is None:
        return None
    lookup = {key.lower() for key in keys}
    try:
        actual_keys = mapping.keys()
    except Exception:
        return None
    for actual_key in actual_keys:
        if str(actual_key).lower() not in lookup:
            continue
        try:
            value = mapping.get(actual_key)
        except Exception:
            continue
        parsed = _coerce_number(value)
        if parsed is not None:
            return parsed
    return None


def _custom_export_number(target, keys):
    direct = _mapping_export_number(target, keys)
    if direct is not None:
        return direct

    group_lookup = {key.lower() for key in _CUSTOM_RENDER_GROUP_KEYS}
    try:
        actual_keys = target.keys()
    except Exception:
        actual_keys = []
    for actual_key in actual_keys:
        if str(actual_key).lower() not in group_lookup:
            continue
        try:
            nested = target.get(actual_key)
        except Exception:
            continue
        nested_value = _mapping_export_number(nested, keys)
        if nested_value is not None:
            return nested_value

    for key in keys:
        try:
            parsed = _coerce_number(getattr(target, key))
        except Exception:
            parsed = None
        if parsed is not None:
            return parsed
    return None


def _coerce_size(value):
    if isinstance(value, str):
        normalized = value.lower().replace("*", "x").replace(",", "x")
        parts = [part.strip() for part in normalized.split("x") if part.strip()]
        if len(parts) >= 2:
            width = _coerce_number(parts[0])
            height = _coerce_number(parts[1])
            if width and height:
                return width, height
        return None

    try:
        if len(value) >= 2:
            width = _coerce_number(value[0])
            height = _coerce_number(value[1])
            if width and height:
                return width, height
    except Exception:
        pass

    width = _mapping_export_number(value, _CUSTOM_RENDER_WIDTH_KEYS)
    height = _mapping_export_number(value, _CUSTOM_RENDER_HEIGHT_KEYS)
    if width and height:
        return width, height
    return None


def _custom_size(target):
    lookup = {key.lower() for key in _CUSTOM_RENDER_SIZE_KEYS}
    try:
        actual_keys = target.keys()
    except Exception:
        actual_keys = []
    for actual_key in actual_keys:
        if str(actual_key).lower() not in lookup:
            continue
        try:
            size = _coerce_size(target.get(actual_key))
        except Exception:
            size = None
        if size:
            return size

    group_lookup = {key.lower() for key in _CUSTOM_RENDER_GROUP_KEYS}
    for actual_key in actual_keys:
        if str(actual_key).lower() not in group_lookup:
            continue
        try:
            nested = target.get(actual_key)
        except Exception:
            continue
        size = _coerce_size(nested)
        if size:
            return size

    width = _custom_export_number(target, _CUSTOM_RENDER_WIDTH_KEYS)
    height = _custom_export_number(target, _CUSTOM_RENDER_HEIGHT_KEYS)
    if width and height:
        return width, height
    return None


def _selected_camera_export_targets(scene):
    camera = getattr(scene, "jimeng_camera", None)
    targets = []
    if camera is not None:
        try:
            for marker in scene.timeline_markers:
                if getattr(marker, "camera", None) == camera:
                    targets.append(marker)
        except Exception:
            pass
        targets.append(camera)
        data = getattr(camera, "data", None)
        if data is not None:
            targets.append(data)
    return targets


def selected_camera_export_parameters(scene):
    render = scene.render
    default_width = int(getattr(render, "resolution_x", 0) or 0)
    default_height = int(getattr(render, "resolution_y", 0) or 0)
    default_percentage = int(getattr(render, "resolution_percentage", 100) or 100)

    for target in _selected_camera_export_targets(scene):
        size = _custom_size(target)
        percentage = _custom_export_number(target, _CUSTOM_RENDER_PERCENTAGE_KEYS)
        if size:
            return int(round(size[0])), int(round(size[1])), int(round(percentage or 100))
        if percentage:
            return default_width, default_height, int(round(percentage))

    return default_width, default_height, default_percentage


def sync_selected_camera_export_parameters(scene, sync_frame_range=None):
    """Refresh UI export parameters from the current Blender scene/camera."""
    changed = False
    width, height, percentage = selected_camera_export_parameters(scene)
    if width > 0 and height > 0:
        width = int(width)
        height = int(height)
        percentage = max(1, int(percentage))
        if int(getattr(scene.render, "resolution_x", 0) or 0) != width:
            scene.render.resolution_x = width
            changed = True
        if int(getattr(scene.render, "resolution_y", 0) or 0) != height:
            scene.render.resolution_y = height
            changed = True
        if int(getattr(scene.render, "resolution_percentage", 0) or 0) != percentage:
            scene.render.resolution_percentage = percentage
            changed = True

    if sync_frame_range is None:
        sync_frame_range = not getattr(scene, "jimeng_frame_range_manual", False)

    if sync_frame_range:
        start, end = selected_camera_frame_range(scene)
        if (
            int(getattr(scene, "jimeng_frame_start", 0) or 0) != int(start)
            or int(getattr(scene, "jimeng_frame_end", 0) or 0) != int(end)
            or not getattr(scene, "jimeng_frame_range_initialized", False)
        ):
            _set_frame_range_from_source(scene, start, end)
            changed = True
    else:
        ensure_frame_range_properties(scene)

    before_clamp = (
        int(getattr(scene, "jimeng_frame_start", 0) or 0),
        int(getattr(scene, "jimeng_frame_end", 0) or 0),
    )
    clamped_start, clamped_end = clamp_frame_range(scene)
    if (clamped_start, clamped_end) != before_clamp:
        changed = True
    return changed


def selected_frame_range(scene):
    ensure_frame_range_properties(scene)
    frame_start = int(scene.jimeng_frame_start)
    frame_end = int(scene.jimeng_frame_end)
    if frame_start > frame_end:
        raise ValueError("Frame Start must be less than or equal to Frame End.")
    frame_count = frame_end - frame_start + 1
    limit = effective_frame_limit(scene)
    if frame_count > limit:
        raise ValueError(
            "Frame range exceeds selected camera max frames: {0} > {1}".format(
                frame_count,
                limit,
            )
        )
    return frame_start, frame_end


_CUSTOM_FRAME_START_KEYS = (
    "frame_start",
    "start_frame",
    "startFrame",
    "shot_start",
    "shotStart",
    "shot_frame_start",
)
_CUSTOM_FRAME_END_KEYS = (
    "frame_end",
    "end_frame",
    "endFrame",
    "shot_end",
    "shotEnd",
    "shot_frame_end",
)


def _custom_number(target, keys):
    if target is None:
        return None
    lookup = {key.lower(): key for key in keys}
    try:
        for actual_key in target.keys():
            expected = lookup.get(str(actual_key).lower())
            if expected:
                value = target.get(actual_key)
                return float(value)
    except Exception:
        pass
    for key in keys:
        try:
            if hasattr(target, key):
                return float(getattr(target, key))
        except Exception:
            pass
    return None


def _custom_frame_range(target):
    start = _custom_number(target, _CUSTOM_FRAME_START_KEYS)
    end = _custom_number(target, _CUSTOM_FRAME_END_KEYS)
    if start is None or end is None:
        return None
    if start > end:
        start, end = end, start
    return int(round(start)), int(round(end))


def _timeline_marker_frame_range(scene, camera):
    if camera is None:
        return None
    try:
        markers = sorted(scene.timeline_markers, key=lambda marker: int(marker.frame))
    except Exception:
        return None

    ranges = []
    for index, marker in enumerate(markers):
        if getattr(marker, "camera", None) != camera:
            continue
        start = int(marker.frame)
        if index + 1 < len(markers):
            end = int(markers[index + 1].frame) - 1
        else:
            end = int(scene.frame_end)
        if end >= start:
            ranges.append((start, end))

    if not ranges:
        return None
    return min(item[0] for item in ranges), max(item[1] for item in ranges)


def selected_camera_frame_range(scene):
    camera = getattr(scene, "jimeng_camera", None)
    targets = [camera, getattr(camera, "data", None) if camera else None]

    for target in targets:
        custom_range = _custom_frame_range(target)
        if custom_range:
            return custom_range

    marker_range = _timeline_marker_frame_range(scene, camera)
    if marker_range:
        return marker_range

    return int(scene.frame_start), int(scene.frame_end)


def selected_camera_frame_count(scene):
    start, end = selected_camera_frame_range(scene)
    return max(1, int(end) - int(start) + 1)


def protocol_frame_limit(scene):
    protocol_limit = int(
        getattr(scene, "jimeng_dcc_max_frame_num", 0)
        or dcc_config.DEFAULT_DURATION * dcc_config.DEFAULT_FPS
    )
    if protocol_limit <= 0:
        protocol_limit = dcc_config.DEFAULT_DURATION * dcc_config.DEFAULT_FPS
    return max(1, protocol_limit)


def min_frame_limit(scene):
    try:
        value = int(getattr(scene, "jimeng_dcc_min_frame_num", 0) or 0)
    except Exception:
        value = 0
    return max(1, value or dcc_config.DEFAULT_MIN_FRAME_NUM)


def selected_ui_frame_count(scene):
    try:
        start = int(getattr(scene, "jimeng_frame_start", scene.frame_start))
        end = int(getattr(scene, "jimeng_frame_end", scene.frame_end))
    except Exception:
        return 0
    return max(0, end - start + 1)


def selected_ui_frame_range_too_short(scene):
    return selected_ui_frame_count(scene) < min_frame_limit(scene)


def effective_frame_limit(scene):
    protocol_limit = protocol_frame_limit(scene)
    return max(1, min(protocol_limit, selected_camera_frame_count(scene)))


def frame_limit_label(scene):
    return str(protocol_frame_limit(scene))


def clamp_frame_range(scene):
    start = int(getattr(scene, "jimeng_frame_start", scene.frame_start))
    end = int(getattr(scene, "jimeng_frame_end", scene.frame_end))
    if start > end:
        end = start

    limit = effective_frame_limit(scene)
    if end - start + 1 > limit:
        end = start + limit - 1
    if (
        int(getattr(scene, "jimeng_frame_start", 0) or 0) != start
        or int(getattr(scene, "jimeng_frame_end", 0) or 0) != end
    ):
        _set_frame_range_from_source(scene, start, end, initialized=False)
    return start, end


def _save_scene_config(scene):
    settings.save_config(
        {
            "video_path": bpy.path.abspath(scene.jimeng_video_path),
            "output_dir": bpy.path.abspath(scene.jimeng_output_dir),
        }
    )


def _load_scene_config(scene):
    config = settings.load_config()
    if config.get("video_path"):
        scene.jimeng_video_path = config["video_path"]
    if config.get("output_dir"):
        scene.jimeng_output_dir = config["output_dir"]
    scene.jimeng_resolution = dcc_config.DEFAULT_RESOLUTION_KEY


def _validate_video_path(path):
    path = bpy.path.abspath(path)
    if not path:
        raise ValueError("Choose a video file first.")
    if not os.path.exists(path):
        raise ValueError("Video file does not exist: {0}".format(path))
    _root, ext = os.path.splitext(path)
    if ext.lower() not in settings.SUPPORTED_VIDEO_EXTENSIONS:
        raise ValueError("Unsupported video extension: {0}".format(ext))
    return path, ext.lower()


class JIMENG_OT_load_config(bpy.types.Operator):
    bl_idname = "jimeng.load_config"
    bl_label = "Load Saved Settings"

    def execute(self, context):
        _load_scene_config(context.scene)
        return {"FINISHED"}


class JIMENG_OT_use_scene_frame_range(bpy.types.Operator):
    bl_idname = "jimeng.use_scene_frame_range"
    bl_label = "Use Scene Range"
    bl_description = "Use the Blender scene timeline range for Jimeng viewport rendering"

    def execute(self, context):
        scene = context.scene
        start, end = selected_camera_frame_range(scene)
        _set_frame_range_from_source(scene, int(start), int(end))
        scene.jimeng_frame_range_manual = False
        start, end = clamp_frame_range(scene)
        scene.jimeng_status = "Frame range synced: {0}-{1}".format(
            start,
            end,
        )
        return {"FINISHED"}


class JIMENG_OT_set_uploader_mode(bpy.types.Operator):
    bl_idname = "jimeng.set_uploader_mode"
    bl_label = "Set Upload Mode"
    bl_description = "Switch Jimeng/Dreamina uploader mode"

    mode: bpy.props.EnumProperty(
        items=(
            ("VIEWPORT", "相机渲染", ""),
            ("EXISTING", "本地上传", ""),
        )
    )

    @classmethod
    def description(cls, _context, properties):
        if getattr(properties, "mode", "") == "VIEWPORT":
            return variant.text("mode_camera")
        if getattr(properties, "mode", "") == "EXISTING":
            return variant.text("mode_local")
        return cls.bl_description

    def execute(self, context):
        context.scene.jimeng_uploader_mode = self.mode
        return {"FINISHED"}


class JIMENG_OT_toggle_default_params(bpy.types.Operator):
    bl_idname = "jimeng.toggle_default_params"
    bl_label = "默认参数"
    bl_description = "Show or hide default Jimeng/Dreamina protocol parameters"

    def execute(self, context):
        scene = context.scene
        scene.jimeng_default_params_expanded = not scene.jimeng_default_params_expanded
        return {"FINISHED"}


class JIMENG_OT_upload_existing(bpy.types.Operator):
    bl_idname = "jimeng.upload_existing"
    bl_label = "上传至即梦生成"
    bl_description = ""

    def execute(self, context):
        scene = context.scene
        stage = "existing"
        try:
            _clear_run_status(scene)
            state.clear_link(scene, reset_task=False)
            _set_task(scene, "RUNNING", "", "")

            stage = "config"
            _append_status(scene, "config", "progress", "Fetching DCC protocol config")
            config = dcc_config.fetch_dcc_protocol_config(settings.DEFAULT_TARGET_URL)
            dcc_config.validate_export_protocol(config)
            update_dcc_protocol_properties(scene, config)
            if config.get("source") == "fallback":
                _append_status(scene, "config", "fallback", config.get("warning") or "Using default DCC protocol")
            else:
                _append_status(scene, "config", "success", "Loaded DCC protocol config")

            video_path, _ext = _validate_video_path(scene.jimeng_video_path)

            stage = "existing"
            _save_scene_config(scene)
            _append_status(scene, "export", "success", "Using local file: {0}".format(video_path))
            video_path = upload_bridge.standardize_mp4(video_path)
            state.clear_link(scene, reset_task=False)
            stage = "bridge"
            _append_status(scene, "bridge", "progress", "Starting local bridge")
            result = upload_bridge.start_local_bridge(
                video_path,
                dcc_config.prompt_for_export(config, ""),
                settings.DEFAULT_TARGET_URL,
                max_file_size=dcc_config.video_protocol(config).get("file_size"),
            )
            scene.jimeng_redirect_url = result.get("redirect_url") or ""
            scene.jimeng_redirect_url_display = scene.jimeng_redirect_url
            scene.jimeng_link_ready = bool(scene.jimeng_redirect_url)
            _append_status(scene, "bridge", "success", "Dreamina link is ready")
            state.mark_link_success(scene)
            self.report({"INFO"}, "Dreamina link is ready.")
            return {"FINISHED"}
        except dcc_config.DccConfigError as exc:
            _append_status(scene, "validate", "failed", str(exc))
            _set_task(scene, "FAILED", "", _friendly_error(scene, exc, stage))
            self.report({"ERROR"}, str(exc))
            print(traceback.format_exc())
            return {"CANCELLED"}
        except Exception as exc:
            _append_status(scene, "failed", "error", str(exc))
            _set_task(scene, "FAILED", "", _friendly_error(scene, exc, stage))
            self.report({"ERROR"}, str(exc))
            print(traceback.format_exc())
            return {"CANCELLED"}


class JIMENG_OT_render_upload(bpy.types.Operator):
    bl_idname = "jimeng.render_upload"
    bl_label = "渲染"
    bl_description = ""

    def execute(self, context):
        scene = context.scene
        stage = "render"
        try:
            _clear_run_status(scene)
            state.clear_link(scene, reset_task=False)
            _set_task(scene, "RUNNING", "", "")

            _save_scene_config(scene)
            stage = "config"
            _append_status(scene, "config", "progress", "Fetching DCC protocol config")
            config = dcc_config.fetch_dcc_protocol_config(settings.DEFAULT_TARGET_URL)
            dcc_config.validate_export_protocol(config)
            update_dcc_protocol_properties(scene, config)
            sync_selected_camera_export_parameters(scene, sync_frame_range=False)
            if config.get("source") == "fallback":
                _append_status(scene, "config", "fallback", config.get("warning") or "Using default DCC protocol")
            else:
                _append_status(scene, "config", "success", "Loaded DCC protocol config")

            frame_start, frame_end = selected_frame_range(scene)
            dcc_config.validate_frame_range(config, frame_start, frame_end)
            stage = "render"
            _append_status(scene, "export", "progress", "Rendering frames {0}-{1}".format(frame_start, frame_end))
            video_path = viewport_render.render_preview_movie(scene, config)
            scene.jimeng_video_path = video_path
            stage = "validate"
            dcc_config.validate_file_size(video_path, config)
            _append_status(
                scene,
                "export",
                "success",
                "Created {0} ({1})".format(video_path, dcc_config.format_bytes(os.path.getsize(video_path))),
            )
            state.clear_link(scene, reset_task=False)
            stage = "bridge"
            _append_status(scene, "bridge", "progress", "Starting local bridge")
            result = upload_bridge.start_local_bridge(
                video_path,
                dcc_config.prompt_for_export(config, ""),
                settings.DEFAULT_TARGET_URL,
                max_file_size=dcc_config.video_protocol(config).get("file_size"),
            )
            scene.jimeng_redirect_url = result.get("redirect_url") or ""
            scene.jimeng_redirect_url_display = scene.jimeng_redirect_url
            scene.jimeng_link_ready = bool(scene.jimeng_redirect_url)
            _store_camera_cache(scene)
            _append_status(scene, "bridge", "success", "Dreamina link is ready")
            state.mark_link_success(scene)
            self.report({"INFO"}, "Dreamina link is ready.")
            return {"FINISHED"}
        except dcc_config.DccConfigError as exc:
            _append_status(scene, "validate", "failed", str(exc))
            _set_task(scene, "FAILED", "", _friendly_error(scene, exc, stage))
            self.report({"ERROR"}, str(exc))
            print(traceback.format_exc())
            return {"CANCELLED"}
        except Exception as exc:
            _append_status(scene, "failed", "error", str(exc))
            _set_task(scene, "FAILED", "", _friendly_error(scene, exc, stage))
            self.report({"ERROR"}, str(exc))
            print(traceback.format_exc())
            return {"CANCELLED"}


class JIMENG_OT_open_redirect_url(bpy.types.Operator):
    bl_idname = "jimeng.open_redirect_url"
    bl_label = "打开链接"
    bl_description = ""

    def execute(self, context):
        scene = context.scene
        url = getattr(scene, "jimeng_redirect_url", "")
        if not url or not state.link_is_current(scene):
            scene.jimeng_status = "No Jimeng link is ready yet."
            self.report({"ERROR"}, scene.jimeng_status)
            return {"CANCELLED"}

        webbrowser.open(url, new=2)
        self.report({"INFO"}, "Opened Jimeng link in the default browser.")
        return {"FINISHED"}


class JIMENG_OT_preview_video(bpy.types.Operator):
    bl_idname = "jimeng.preview_video"
    bl_label = "预览"
    bl_description = ""

    def execute(self, context):
        scene = context.scene
        video_path = bpy.path.abspath(getattr(scene, "jimeng_video_path", "") or "")
        if not video_path or not os.path.exists(video_path):
            scene.jimeng_status = "No preview video is ready yet."
            self.report({"ERROR"}, scene.jimeng_status)
            return {"CANCELLED"}

        bpy.ops.wm.path_open(filepath=video_path)
        self.report({"INFO"}, "Opened preview video.")
        return {"FINISHED"}


class JIMENG_OT_copy_redirect_url(bpy.types.Operator):
    bl_idname = "jimeng.copy_redirect_url"
    bl_label = "复制链接"
    bl_description = "Copy the generated Jimeng/Dreamina link"

    def execute(self, context):
        scene = context.scene
        url = getattr(scene, "jimeng_redirect_url", "")
        if not url or not state.link_is_current(scene):
            scene.jimeng_status = "No Jimeng link is ready yet."
            self.report({"ERROR"}, scene.jimeng_status)
            return {"CANCELLED"}

        context.window_manager.clipboard = url
        self.report({"INFO"}, "Jimeng link copied.")
        return {"FINISHED"}


CLASSES = (
    JIMENG_OT_load_config,
    JIMENG_OT_use_scene_frame_range,
    JIMENG_OT_set_uploader_mode,
    JIMENG_OT_toggle_default_params,
    JIMENG_OT_upload_existing,
    JIMENG_OT_render_upload,
    JIMENG_OT_open_redirect_url,
    JIMENG_OT_preview_video,
    JIMENG_OT_copy_redirect_url,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
