"""DCC protocol config client shared by the Blender add-on."""

from __future__ import annotations

import json
import os
import http.client
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


DCC_CONFIG_PATH = "/mweb/v1/get_dcc_protocol_config"
DEFAULT_CONFIG_QUERY = {"need_install_packages": "false"}
DEFAULT_CONFIG_URL = "https://jimeng.jianying.com" + DCC_CONFIG_PATH
DEFAULT_CONFIG_HEADERS = {
    "content-type": "application/json",
    "x-use-ppe": "1",
    "x-tt-env": "ppe_dreamina_support_blender",
}
DEFAULT_PROMPT = "A cinematic high quality video"
DEFAULT_FILE_SIZE = 200 * 1024 * 1024
DEFAULT_FPS = 24
DEFAULT_DURATION = 30
DEFAULT_MIN_DURATION_SECONDS = 1.8
DEFAULT_MIN_FRAME_NUM = 44
DEFAULT_RESOLUTION_KEY = "720p"
DEFAULT_RESOLUTION_LABEL = "720P"
DEFAULT_CONTAINER_FORMAT = "mp4"
DEFAULT_CODEC = "h264"
DEFAULT_RESOLUTIONS = (
    {"key": "360p", "label": "360P", "short_edge": 360, "width": 640, "height": 360},
    {"key": "480p", "width": 854, "height": 480},
    {"key": "720p", "width": 1280, "height": 720},
    {"key": "1080p", "label": "1080P", "short_edge": 1080, "width": 1920, "height": 1080},
    {"key": "origin", "label": "Origin", "origin": True, "short_edge": 0, "width": 0, "height": 0},
)
FALLBACK_RESPONSE_DATA = {
    "video_protocol": {
        "resolution_list": [
            dict(item) for item in DEFAULT_RESOLUTIONS
        ],
        "fps": 24,
        "container_format": "mp4",
        "codec": "h264",
        "file_size": 209715200,
        "duration": 30,
        "min_frame_num": DEFAULT_MIN_FRAME_NUM,
        "max_frame_num": 720,
    },
    "default_prompt": "A cinematic high quality video",
}
SUPPORTED_RESOLUTION_KEYS = tuple(item["key"] for item in DEFAULT_RESOLUTIONS)
USER_RESOLUTION_SPECS = {
    item["key"]: dict(item)
    for item in DEFAULT_RESOLUTIONS
}


class DccConfigError(RuntimeError):
    pass


def _default_video_protocol():
    return {
        "resolution_list": [dict(item) for item in DEFAULT_RESOLUTIONS],
        "fps": DEFAULT_FPS,
        "container_format": DEFAULT_CONTAINER_FORMAT,
        "codec": DEFAULT_CODEC,
        "file_size": DEFAULT_FILE_SIZE,
        "duration": DEFAULT_DURATION,
        "min_frame_num": DEFAULT_MIN_FRAME_NUM,
        "max_frame_num": DEFAULT_DURATION * DEFAULT_FPS,
    }


def fallback_config(reason=""):
    return normalize_config(FALLBACK_RESPONSE_DATA, source="fallback", warning=reason)


def _as_int(value, fallback):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else fallback
    except Exception:
        return fallback


def normalize_resolution_key(key, fallback=DEFAULT_RESOLUTION_KEY):
    value = str(key or "").strip().lower()
    if value in ("origin", "original", "source"):
        return "origin"
    if value in ("360", "480", "720", "1080"):
        value = value + "p"
    return value if value in SUPPORTED_RESOLUTION_KEYS else fallback


def _normalize_resolution_list(value):
    by_key = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            key = normalize_resolution_key(item.get("key"), "")
            if not key or key not in SUPPORTED_RESOLUTION_KEYS:
                continue
            default_item = USER_RESOLUTION_SPECS[key]
            if key == "origin":
                by_key[key] = dict(default_item)
                continue
            width = _as_int(item.get("width"), default_item.get("width", 0))
            height = _as_int(item.get("height"), default_item.get("height", 0))
            short_edge = _as_int(item.get("short_edge"), min(width, height))
            if width > 0 and height > 0 and short_edge > 0:
                normalized = dict(default_item)
                normalized.update({"key": key, "width": width, "height": height, "short_edge": short_edge})
                by_key[key] = normalized

    for item in DEFAULT_RESOLUTIONS:
        by_key.setdefault(item["key"], dict(item))
    return [by_key[key] for key in SUPPORTED_RESOLUTION_KEYS]


def normalize_config(data, source="remote", warning=""):
    if not isinstance(data, dict):
        data = {}
    video = data.get("video_protocol")
    if not isinstance(video, dict):
        video = {}

    fps = _as_int(video.get("fps"), DEFAULT_FPS)
    duration = _as_int(video.get("duration"), DEFAULT_DURATION)
    min_frame_num = _as_int(video.get("min_frame_num"), DEFAULT_MIN_FRAME_NUM)
    max_frame_num = _as_int(video.get("max_frame_num"), duration * fps)
    file_size = _as_int(video.get("file_size"), DEFAULT_FILE_SIZE)
    container_format = str(video.get("container_format") or DEFAULT_CONTAINER_FORMAT).lower()
    codec = str(video.get("codec") or DEFAULT_CODEC).lower()

    return {
        "video_protocol": {
            "resolution_list": _normalize_resolution_list(video.get("resolution_list")),
            "fps": fps,
            "container_format": container_format,
            "codec": codec,
            "file_size": file_size,
            "duration": duration,
            "min_frame_num": min_frame_num,
            "max_frame_num": max_frame_num,
        },
        "default_prompt": str(data.get("default_prompt") or DEFAULT_PROMPT),
        "source": source,
        "warning": warning,
    }


def export_resolution_spec(key):
    return dict(
        USER_RESOLUTION_SPECS.get(normalize_resolution_key(key))
        or USER_RESOLUTION_SPECS[DEFAULT_RESOLUTION_KEY]
    )


def resolution_spec(_config, key):
    return export_resolution_spec(key)


def video_protocol(config):
    return (config or {}).get("video_protocol") or _default_video_protocol()


def prompt_for_export(config, prompt):
    text = (prompt or "").strip()
    if text:
        return text
    return (config or {}).get("default_prompt") or DEFAULT_PROMPT


def validate_export_protocol(config):
    protocol = video_protocol(config)
    container = str(protocol.get("container_format") or "").lower()
    codec = str(protocol.get("codec") or "").lower()
    if container != "mp4":
        raise DccConfigError("Unsupported DCC container_format: {0}".format(container))
    if codec not in ("h264", "h.264", "avc", "avc1", "libx264"):
        raise DccConfigError("Unsupported DCC codec: {0}".format(codec))


def validate_frame_range(config, start_frame, end_frame):
    protocol = video_protocol(config)
    min_frame_num = _as_int(protocol.get("min_frame_num"), DEFAULT_MIN_FRAME_NUM)
    max_frame_num = _as_int(protocol.get("max_frame_num"), 0)
    start = int(start_frame)
    end = int(end_frame)
    if start > end:
        raise DccConfigError("Frame Start must be less than or equal to Frame End.")
    frame_count = end - start + 1
    if min_frame_num > 0 and frame_count < min_frame_num:
        raise DccConfigError(
            "Frame range is shorter than DCC min_frame_num: {0} < {1}".format(
                frame_count,
                min_frame_num,
            )
        )
    if max_frame_num > 0 and frame_count > max_frame_num:
        raise DccConfigError(
            "Frame range exceeds DCC max_frame_num: {0} > {1}".format(
                frame_count,
                max_frame_num,
            )
        )


def validate_file_size(path, config):
    limit = _as_int(video_protocol(config).get("file_size"), DEFAULT_FILE_SIZE)
    if limit <= 0 or not os.path.exists(path):
        return
    size = os.path.getsize(path)
    if size > limit:
        raise DccConfigError(
            "Exported file is too large: {0} > {1}".format(
                format_bytes(size),
                format_bytes(limit),
            )
        )


def format_bytes(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return "{0:.1f}{1}".format(value, unit) if unit != "B" else "{0}B".format(int(value))
        value /= 1024
    return "{0}B".format(size)


def _with_default_query(url):
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in DEFAULT_CONFIG_QUERY.items():
        query.setdefault(key, value)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query),
            parsed.fragment,
        )
    )


def _candidate_urls(target_url=None):
    env_url = os.environ.get("JIMENG_DCC_CONFIG_URL", "").strip()
    urls = []
    if env_url:
        urls.append(env_url)

    if target_url:
        try:
            parsed = urlparse(target_url)
            if parsed.scheme and parsed.netloc:
                urls.append("{0}://{1}{2}".format(parsed.scheme, parsed.netloc, DCC_CONFIG_PATH))
        except Exception:
            pass

    urls.append(DEFAULT_CONFIG_URL)
    deduped = []
    for url in urls:
        normalized_url = _with_default_query(url) if url else ""
        if normalized_url and normalized_url not in deduped:
            deduped.append(normalized_url)
    return deduped


def _post_json(url, payload, timeout):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise DccConfigError("Invalid DCC config URL: {0}".format(url))

    path = parsed.path or "/"
    if parsed.query:
        path = "{0}?{1}".format(path, parsed.query)

    connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_cls(parsed.netloc, timeout=timeout)
    try:
        connection.request("POST", path, body=payload, headers=DEFAULT_CONFIG_HEADERS)
        response = connection.getresponse()
        body = response.read().decode("utf-8", "replace")
        if response.status < 200 or response.status >= 300:
            raise DccConfigError("HTTP {0}: {1}".format(response.status, body[:200]))
        return body
    finally:
        connection.close()


def fetch_dcc_protocol_config(target_url=None, timeout=5):
    errors = []
    payload = json.dumps({}).encode("utf-8")
    for url in _candidate_urls(target_url):
        try:
            body = _post_json(url, payload, timeout)
            parsed = json.loads(body)
            if isinstance(parsed, dict) and str(parsed.get("ret", "0")) != "0":
                raise DccConfigError(
                    "DCC config response ret={0}: {1}".format(
                        parsed.get("ret"),
                        parsed.get("errmsg", ""),
                    )
                )
            data = parsed.get("data") if isinstance(parsed, dict) else None
            if not isinstance(data, dict):
                raise DccConfigError("DCC config response has no data field")
            return normalize_config(data, source=url)
        except Exception as exc:
            errors.append("{0}: {1}".format(url, exc))

    return fallback_config("; ".join(errors))
