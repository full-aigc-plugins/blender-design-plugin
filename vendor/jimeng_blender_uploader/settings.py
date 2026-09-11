"""Shared defaults for the Blender uploader add-on."""

from __future__ import annotations

import json
import os

from . import variant

DEFAULT_TARGET_URL = variant.TARGET_URL
SUPPORTED_VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".avi")


def user_config_dir():
    return os.path.join(os.path.expanduser("~"), ".jimeng_blender_uploader")


def config_path():
    return os.path.join(user_config_dir(), "config.json")


def load_config():
    path = config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(data):
    directory = user_config_dir()
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with open(config_path(), "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def default_output_dir():
    directory = os.path.join(user_config_dir(), "playblasts")
    if not os.path.isdir(directory):
        os.makedirs(directory)
    return directory
