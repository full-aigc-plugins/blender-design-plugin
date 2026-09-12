"""Tests for jimeng_link: the link flow using the vendored bridge."""

import os
import sys
import tempfile
import unittest
from unittest import mock

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
for _d in (_SCRIPTS_DIR, _REPO_ROOT):
    if _d not in sys.path:
        sys.path.insert(0, _d)

# Ensure bpy stub exists for vendored module import
if "bpy" not in sys.modules:
    import types
    _stub = types.ModuleType("bpy")
    _stub.app = types.SimpleNamespace(version_string="4.2.0")
    _stub.ops = types.SimpleNamespace(render=types.SimpleNamespace(opengl=lambda **kw: None))
    _stub.path = types.SimpleNamespace(abspath=lambda p: os.path.abspath(os.path.expanduser(p or "")))
    _stub.data = types.SimpleNamespace(objects=[], materials=[])
    _stub.context = types.SimpleNamespace(scene=None)
    sys.modules["bpy"] = _stub

from jimeng_link import produce_jimeng_link
from blender_bridge import BlenderError


class TestProduceJimengLink(unittest.TestCase):
    def test_valid_video_produces_link(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"\x00" * 1024)
            video_path = f.name

        try:
            result = produce_jimeng_link(video_path)
            self.assertIn("redirect_url", result)
            self.assertIn("resource_info_url", result)
            self.assertIn("port", result)
            self.assertGreater(result["port"], 0)
            self.assertIn("jimeng.jianying.com", result["redirect_url"])
        finally:
            os.unlink(video_path)

    def test_missing_video_raises(self):
        with self.assertRaises(BlenderError) as ctx:
            produce_jimeng_link("/nonexistent.mp4")
        self.assertEqual(ctx.exception.category, "RENDER_FAILED")

    def test_empty_video_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            video_path = f.name
        try:
            with self.assertRaises(BlenderError) as ctx:
                produce_jimeng_link(video_path)
            self.assertEqual(ctx.exception.category, "RENDER_FAILED")
        finally:
            os.unlink(video_path)

    def test_custom_prompt_used(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"\x00" * 1024)
            video_path = f.name
        try:
            result = produce_jimeng_link(video_path, prompt="Custom prompt text")
            self.assertEqual(result["prompt"], "Custom prompt text")
        finally:
            os.unlink(video_path)


if __name__ == "__main__":
    unittest.main()
