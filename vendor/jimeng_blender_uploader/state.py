"""Shared UI state helpers for the Blender uploader."""

from __future__ import annotations

import json

import bpy


def _camera_key(scene):
    camera = getattr(scene, "jimeng_camera", None)
    if not camera:
        return ""
    return getattr(camera, "name_full", None) or getattr(camera, "name", "")


def _absolute_path(value):
    try:
        return bpy.path.abspath(value or "")
    except Exception:
        return value or ""


def input_signature(scene):
    mode = getattr(scene, "jimeng_uploader_mode", "VIEWPORT") or "VIEWPORT"
    data = {"mode": mode}
    if mode == "EXISTING":
        data["video_path"] = _absolute_path(getattr(scene, "jimeng_video_path", ""))
    else:
        render = scene.render
        data.update(
            {
                "camera": _camera_key(scene),
                "resolution": getattr(scene, "jimeng_resolution", "") or "",
                "frame_start": int(getattr(scene, "jimeng_frame_start", 0) or 0),
                "frame_end": int(getattr(scene, "jimeng_frame_end", 0) or 0),
                "output_dir": _absolute_path(getattr(scene, "jimeng_output_dir", "")),
                "render_resolution_x": int(getattr(render, "resolution_x", 0) or 0),
                "render_resolution_y": int(getattr(render, "resolution_y", 0) or 0),
                "render_resolution_percentage": int(
                    getattr(render, "resolution_percentage", 0) or 0
                ),
            }
        )
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def set_task(scene, state, message="", error=""):
    scene.jimeng_task_state = state
    scene.jimeng_task_message = message
    scene.jimeng_error_message = error


def clear_link(scene, reset_task=True):
    scene.jimeng_redirect_url = ""
    scene.jimeng_redirect_url_display = ""
    scene.jimeng_link_ready = False
    scene.jimeng_link_signature = ""
    if reset_task:
        set_task(scene, "IDLE", "", "")


def mark_link_success(scene):
    scene.jimeng_link_signature = input_signature(scene)
    set_task(scene, "SUCCESS", "", "")


def link_is_current(scene):
    if getattr(scene, "jimeng_task_state", "IDLE") != "SUCCESS":
        return False
    if not (getattr(scene, "jimeng_link_ready", False) and getattr(scene, "jimeng_redirect_url", "")):
        return False
    signature = getattr(scene, "jimeng_link_signature", "") or ""
    return bool(signature and signature == input_signature(scene))
