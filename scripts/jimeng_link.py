"""Jimeng link flow: produce a ready-to-open Jimeng link for a preview video.

Reuses the vendored upload_bridge's local HTTP bridge to serve the video
and construct the redirect URL.
"""

import os
import sys
from pathlib import Path


def produce_jimeng_link(video_path, prompt=None, target_url=None):
    """Start a local bridge and return the Jimeng link info.

    Args:
        video_path: Path to the validated MP4 file.
        prompt: Optional prompt text (uses default if empty).
        target_url: Optional target URL override.

    Returns:
        dict with keys: redirect_url, resource_info_url, port, video, prompt

    Raises:
        BlenderError if the video is missing or the bridge fails.
    """
    from vendor.jimeng_blender_uploader import upload_bridge, dcc_config, variant

    video = Path(video_path)
    if not video.exists():
        raise _link_error("RENDER_FAILED", f"video file not found: {video_path}")
    if video.stat().st_size == 0:
        raise _link_error("RENDER_FAILED", f"video file is empty: {video_path}")

    effective_prompt = prompt or dcc_config.DEFAULT_PROMPT
    effective_target = target_url or variant.TARGET_URL

    try:
        result = upload_bridge.start_local_bridge(
            str(video.resolve()),
            effective_prompt,
            effective_target,
        )
    except upload_bridge.UploadError as exc:
        raise _link_error("RENDER_FAILED", str(exc))
    except Exception as exc:
        raise _link_error("RENDER_FAILED", f"bridge failed: {exc}")

    return {
        "redirect_url": result.get("redirect_url", ""),
        "resource_info_url": result.get("resource_info_url", ""),
        "port": result.get("port", 0),
        "video": result.get("video", ""),
        "prompt": effective_prompt,
    }


def _link_error(category, message):
    """Create a BlenderError for link failures."""
    # Import from blender_bridge to reuse the exception class
    from blender_bridge import BlenderError
    return BlenderError(category, message)
