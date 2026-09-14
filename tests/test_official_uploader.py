"""Behavior tests for runtime-only delegation to the official Jimeng uploader."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.harness.errors import HarnessError
from scripts.harness.runtime import build_registry


class _Operator:
    def __init__(self, result=None):
        self.calls = 0
        self.result = result or {"FINISHED"}

    def __call__(self):
        self.calls += 1
        return self.result


def _bpy(*, installed=True, current_link=True, addon_module="jimeng_blender_uploader"):
    render = _Operator()
    existing = _Operator()
    open_link = _Operator()
    jimeng = SimpleNamespace(
        render_upload=render,
        upload_existing=existing,
        open_redirect_url=open_link,
    )
    scene = SimpleNamespace(
        jimeng_camera=None,
        jimeng_resolution="720p",
        jimeng_frame_start=1,
        jimeng_frame_end=48,
        jimeng_output_dir="",
        jimeng_video_path="",
        jimeng_prompt="",
        jimeng_task_state="SUCCEEDED" if current_link else "IDLE",
        jimeng_error_message="",
        jimeng_link_ready=current_link,
        jimeng_redirect_url=(
            "https://jimeng.jianying.com/ai-tool/home?channel=blender&thirdparty_id=secret"
            if current_link else ""
        ),
    )
    camera = SimpleNamespace(name="Camera", type="CAMERA")
    addons = {}
    if installed:
        addons["jimeng_blender_uploader"] = SimpleNamespace(module=addon_module)
    return SimpleNamespace(
        app=SimpleNamespace(version=(5, 2, 1)),
        context=SimpleNamespace(scene=scene, preferences=SimpleNamespace(addons=addons)),
        data=SimpleNamespace(objects=[camera], materials=[], collections=[], images=[]),
        ops=SimpleNamespace(jimeng=jimeng),
        path=SimpleNamespace(abspath=lambda value: value),
        _operators=(render, existing, open_link),
    )


class OfficialUploaderCommandTests(unittest.TestCase):
    def _registry(self, bpy, command):
        sys.modules["jimeng_blender_uploader"] = SimpleNamespace(bl_info={"version": (1, 0, 0), "blender": (5, 2, 0)})
        self.addCleanup(sys.modules.pop, "jimeng_blender_uploader", None)
        registry = build_registry(bpy, runtime_mode="connector", approved_output_root=Path("/tmp"), approved_asset_roots=(Path("/tmp"),))
        names = {entry["command"] for entry in registry.capabilities()}
        self.assertIn(command, names, f"missing production command {command}")
        return registry

    def test_absent_addon_fails_closed(self):
        registry = self._registry(_bpy(installed=False), "official_uploader.inspect")
        with self.assertRaises(HarnessError) as raised:
            registry.dispatch("official_uploader.inspect", {})
        self.assertEqual(raised.exception.code, "OFFICIAL_UPLOADER_NOT_AVAILABLE")

    def test_inspect_reports_version_and_operator_capabilities(self):
        registry = self._registry(_bpy(), "official_uploader.inspect")
        result = registry.dispatch("official_uploader.inspect", {})["result"]
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(
            result["operations"],
            ["render_and_link", "link_existing", "status", "open_link"],
        )

    def test_render_and_link_invokes_official_operator_once(self):
        bpy = _bpy(current_link=False)
        registry = self._registry(bpy, "official_uploader.render_and_link")
        registry.dispatch("official_uploader.render_and_link", {
            "camera": "Camera", "resolution": "720p", "frameStart": 1,
            "frameEnd": 48, "outputDir": "/tmp/output", "prompt": "orbit",
        })
        self.assertEqual(bpy._operators[0].calls, 1)
        self.assertEqual(bpy._operators[1].calls, 0)
        self.assertEqual(bpy._operators[2].calls, 0)

    def test_link_existing_invokes_official_operator_once(self):
        bpy = _bpy(current_link=False)
        registry = self._registry(bpy, "official_uploader.link_existing")
        with tempfile.NamedTemporaryFile(suffix=".mp4", dir="/tmp") as video:
            registry.dispatch("official_uploader.link_existing", {"videoPath": video.name})
        self.assertEqual(bpy._operators[0].calls, 0)
        self.assertEqual(bpy._operators[1].calls, 1)

    def test_status_redacts_the_loopback_token(self):
        registry = self._registry(_bpy(), "official_uploader.status")
        result = registry.dispatch("official_uploader.status", {})["result"]
        self.assertTrue(result["linkReady"])
        self.assertEqual(result["linkOrigin"], "https://jimeng.jianying.com")
        self.assertNotIn("thirdparty_id", str(result))
        self.assertNotIn("secret", str(result))

    def test_open_link_rejects_stale_state(self):
        registry = self._registry(_bpy(current_link=False), "official_uploader.open_link")
        with self.assertRaises(HarnessError) as raised:
            registry.dispatch("official_uploader.open_link", {})
        self.assertEqual(raised.exception.code, "OFFICIAL_LINK_NOT_READY")

    def test_managed_mode_exposes_no_official_uploader_commands(self):
        registry = build_registry(_bpy(), runtime_mode="managed", approved_output_root=Path("/tmp"))
        names = {entry["command"] for entry in registry.capabilities()}
        self.assertFalse(any(name.startswith("official_uploader.") for name in names))

    def test_real_addon_module_string_resolves_version(self):
        registry = self._registry(_bpy(addon_module="jimeng_blender_uploader"), "official_uploader.inspect")
        self.assertEqual(registry.dispatch("official_uploader.inspect", {})["result"]["version"], "1.0.0")

    def test_unsupported_addon_version_is_rejected(self):
        sys.modules["jimeng_blender_uploader"] = SimpleNamespace(bl_info={"version": (0, 9, 0), "blender": (5, 2, 0)})
        self.addCleanup(sys.modules.pop, "jimeng_blender_uploader", None)
        registry = build_registry(_bpy(), runtime_mode="connector", approved_output_root=Path("/tmp"), approved_asset_roots=(Path("/tmp"),))
        with self.assertRaises(HarnessError) as raised:
            registry.dispatch("official_uploader.inspect", {})
        self.assertEqual(raised.exception.code, "OFFICIAL_UPLOADER_UNSUPPORTED")

    def test_unsupported_blender_version_is_rejected(self):
        bpy = _bpy()
        bpy.app.version = (4, 1, 0)
        sys.modules["jimeng_blender_uploader"] = SimpleNamespace(bl_info={"version": (1, 0, 0), "blender": (5, 2, 0)})
        self.addCleanup(sys.modules.pop, "jimeng_blender_uploader", None)
        registry = build_registry(bpy, runtime_mode="connector", approved_output_root=Path("/tmp"), approved_asset_roots=(Path("/tmp"),))
        with self.assertRaises(HarnessError) as raised:
            registry.dispatch("official_uploader.inspect", {})
        self.assertEqual(raised.exception.code, "OFFICIAL_UPLOADER_UNSUPPORTED")

    def test_output_and_video_paths_must_be_inside_approved_roots(self):
        bpy = _bpy(current_link=False)
        sys.modules["jimeng_blender_uploader"] = SimpleNamespace(bl_info={"version": (1, 0, 0), "blender": (5, 2, 0)})
        self.addCleanup(sys.modules.pop, "jimeng_blender_uploader", None)
        with tempfile.TemporaryDirectory() as approved, tempfile.TemporaryDirectory() as outside_dir:
            registry = build_registry(bpy, runtime_mode="connector", approved_output_root=Path(approved), approved_asset_roots=(Path(approved),))
            with self.assertRaises(HarnessError):
                registry.dispatch("official_uploader.render_and_link", {
                    "camera": "Camera", "frameStart": 1, "frameEnd": 48,
                    "outputDir": str(Path(outside_dir) / "output"), "prompt": "secret prompt",
                })
            outside = Path(outside_dir) / "input.mp4"
            outside.write_bytes(b"video")
            with self.assertRaises(HarnessError):
                registry.dispatch("official_uploader.link_existing", {"videoPath": str(outside)})
        self.assertEqual(bpy._operators[0].calls, 0)
        self.assertEqual(bpy._operators[1].calls, 0)


if __name__ == "__main__":
    unittest.main()
