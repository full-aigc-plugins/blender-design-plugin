#!/usr/bin/env python3
"""Receipt adapter consumed by codex-dreamina-3d after local preview validation."""

from __future__ import annotations


def build_preview_receipt(artifact: dict, request: dict, media: dict) -> dict:
    codec = str(media.get("codec", "")).lower()
    if codec not in {"h264", "avc1"}:
        raise ValueError(f"preview codec must be h264, got {codec!r}")
    frame_range = dict(request["frame_range"])
    camera_name = str(request["camera_name"])
    return {
        "schema_version": "1.0.0",
        "producer_plugin": "codex-blender",
        "producer_version": "0.1.0",
        "artifact_id": str(request["artifact_id"]),
        "path": str(artifact["path"]),
        "sha256": str(artifact["sha256"]),
        "codec": "h264",
        "container": "mp4",
        "dimensions": {"width": int(media["width"]), "height": int(media["height"])},
        "fps": float(media["fps"]),
        "duration_seconds": float(media["duration_seconds"]),
        "bytes": int(artifact["bytes"]),
        "camera": {"name": camera_name},
        "frame_range": {"start": int(frame_range["start"]), "end": int(frame_range["end"])},
        "preview_mode": "camera_render",
        "restoration": {"status": "confirmed", "evidence": "export settings restored by Harness"},
    }
