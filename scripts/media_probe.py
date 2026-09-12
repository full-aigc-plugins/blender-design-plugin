"""Media probe: ffprobe-based validation of preview artifacts.

Discovers ffprobe, extracts codec/dimensions/fps/duration, validates
against a protocol profile, and hashes the final bytes.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


class ProbeError(RuntimeError):
    """Raised when probing fails."""
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def discover_ffprobe(explicit_path=None):
    """Find ffprobe on this system.  Returns the path or None.

    Resolution order:
      1. explicit_path (if provided and executable)
      2. JIMENG_FFPROBE environment variable
      3. shutil.which("ffprobe")
      4. hard-coded system paths
    """
    candidates = []
    if explicit_path:
        candidates.append(explicit_path)
    env_path = os.environ.get("JIMENG_FFPROBE", "").strip()
    if env_path:
        candidates.append(env_path)
    which = shutil.which("ffprobe")
    if which:
        candidates.append(which)
    for p in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "/usr/bin/ffprobe"):
        candidates.append(p)

    seen = set()
    for c in candidates:
        c = os.path.normpath(os.path.abspath(c))
        if c in seen:
            continue
        seen.add(c)
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def probe_media(path, ffprobe=None):
    """Probe a media file with ffprobe and return a dict of metadata.

    Args:
        path: Path to the media file.
        ffprobe: Path to ffprobe executable (auto-discovered if None).

    Returns:
        dict with keys: codec, width, height, fps, durationSeconds, bytes

    Raises:
        ProbeError("DEPENDENCY_MISSING") if ffprobe is not found.
        ProbeError("MEDIA_INVALID") if probing fails.
    """
    path = Path(path)
    if not path.exists():
        raise ProbeError("MEDIA_INVALID", f"file not found: {path}")
    if path.stat().st_size == 0:
        raise ProbeError("MEDIA_INVALID", f"file is empty: {path}")

    if ffprobe is None:
        ffprobe = discover_ffprobe()
    if ffprobe is None:
        raise ProbeError("DEPENDENCY_MISSING", "ffprobe not found on this system")

    # Pre-probe stat for tamper detection
    pre_stat = path.stat()

    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
    except subprocess.TimeoutExpired:
        raise ProbeError("MEDIA_INVALID", "ffprobe timed out")
    except OSError as exc:
        raise ProbeError("MEDIA_INVALID", f"ffprobe execution failed: {exc}")

    if result.returncode != 0:
        raise ProbeError("MEDIA_INVALID", f"ffprobe exited with code {result.returncode}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("MEDIA_INVALID", f"ffprobe output not valid JSON: {exc}")

    # Extract video stream info
    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        raise ProbeError("MEDIA_INVALID", "no video stream found")

    vs = video_streams[0]
    fmt = data.get("format", {})

    codec = vs.get("codec_name", "")
    width = int(vs.get("width", 0))
    height = int(vs.get("height", 0))

    # fps: try r_frame_rate first (e.g. "24/1"), then avg_frame_rate
    fps = 0.0
    for key in ("r_frame_rate", "avg_frame_rate"):
        raw = vs.get(key, "")
        if "/" in str(raw):
            num, den = str(raw).split("/", 1)
            try:
                fps = float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                pass
        else:
            try:
                fps = float(raw)
            except (ValueError, TypeError):
                pass
        if fps > 0:
            break

    duration = float(fmt.get("duration", 0) or 0)
    file_bytes = int(fmt.get("size", 0) or 0)
    if file_bytes == 0:
        file_bytes = path.stat().st_size

    # Post-probe tamper check
    post_stat = path.stat()
    if pre_stat.st_size != post_stat.st_size or pre_stat.st_mtime != post_stat.st_mtime:
        raise ProbeError("MEDIA_INVALID", "file changed between probe and hash")

    # SHA-256 of final bytes
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()

    return {
        "codec": codec,
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "durationSeconds": round(duration, 3),
        "bytes": file_bytes,
        "sha256": sha256,
    }


def validate_media(probe, profile):
    """Validate probe results against a protocol profile.

    Args:
        probe: dict from probe_media()
        profile: dict with keys from dcc_config.video_protocol()

    Returns:
        list of error strings (empty = valid)
    """
    errors = []

    # Codec check
    codec = str(probe.get("codec", "")).lower()
    valid_codecs = {"h264", "h.264", "avc", "avc1", "libx264"}
    if codec not in valid_codecs:
        errors.append(f"unsupported codec: {codec}")

    # Container check (we only validate codec, not container format from ffprobe)

    # Dimensions: must be even
    w = probe.get("width", 0)
    h = probe.get("height", 0)
    if w <= 0 or h <= 0:
        errors.append(f"invalid dimensions: {w}x{h}")
    elif w % 2 != 0 or h % 2 != 0:
        errors.append(f"odd dimensions: {w}x{h}")

    # FPS
    fps = probe.get("fps", 0)
    profile_fps = profile.get("fps", 24)
    if fps > 0 and profile_fps > 0:
        if abs(fps - profile_fps) > 1.0:
            errors.append(f"fps mismatch: {fps} vs profile {profile_fps}")

    # Duration
    duration = probe.get("durationSeconds", 0)
    max_duration = profile.get("duration", 30)
    if duration > max_duration + 1.0:
        errors.append(f"duration exceeds limit: {duration}s > {max_duration}s")

    # File size
    file_bytes = probe.get("bytes", 0)
    max_bytes = profile.get("file_size", 200 * 1024 * 1024)
    if file_bytes > max_bytes:
        errors.append(f"file too large: {file_bytes} > {max_bytes}")

    return errors
