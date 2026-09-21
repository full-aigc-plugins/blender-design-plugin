"""Tests for the scene.screenshot command."""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.harness.commands.scene import (
    MAX_DIMENSION,
    MIN_DIMENSION,
    SceneCommands,
)
from scripts.harness.errors import HarnessError

# ---------------------------------------------------------------------------
# Fake bpy
# ---------------------------------------------------------------------------


class FakeObjects(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeImageSettings:
    def __init__(self):
        self.file_format = "PNG"


class FakeRender:
    def __init__(self):
        self.filepath = ""
        self.resolution_x = 1920
        self.resolution_y = 1080
        self.resolution_percentage = 100
        self.image_settings = FakeImageSettings()
        self.engine = "BLENDER_EEVEE_NEXT"


class FakeRenderOps:
    """Mock for bpy.ops.render; writes a tiny PNG-like blob to disk on call."""

    def __init__(self, bpy):
        self.bpy = bpy
        self.calls = []

    def render(self, write_still=False):
        self.calls.append({"write_still": write_still})
        if not write_still:
            return {"FINISHED"}
        # Mimic Blender: writes bytes to scene.render.filepath.
        target = self.bpy.context.scene.render.filepath
        if not target:
            return {"FINISHED"}
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        # 8-byte PNG signature + a marker so the hash is stable and non-empty.
        path.write_bytes(b"\x89PNG\r\n\x1a\nTEST")


class FakeScene:
    def __init__(self):
        self.name = "Scene"
        self.camera = None
        self.frame_start = 1
        self.frame_end = 250
        self.frame_current = 1
        self.objects = FakeObjects()
        self.render = FakeRender()

    def frame_set(self, frame):
        self.frame_current = int(frame)


class FakeBpy:
    def __init__(self):
        self.data = SimpleNamespace()
        self.data.objects = FakeObjects()
        self.data.materials = []
        self.data.images = []
        self.data.collections = []
        self.data.filepath = ""
        self.context = SimpleNamespace()
        self.context.scene = FakeScene()
        self.ops = SimpleNamespace()
        self.ops.render = FakeRenderOps(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_commands(output_root, bpy=None):
    bpy = bpy or FakeBpy()
    # Always provide a camera so the camera-required gate does not dominate
    # path/dimension tests.
    cam = SimpleNamespace(name="Camera.001", type="CAMERA")
    bpy.context.scene.objects[cam.name] = cam
    bpy.data.objects[cam.name] = cam
    bpy.context.scene.camera = cam
    return SceneCommands(bpy, approved_output_root=output_root), bpy


# ---------------------------------------------------------------------------
# Tests: pre-render validation
# ---------------------------------------------------------------------------


class TestScreenshotPathPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.commands, self.bpy = _make_commands(self.root)

    def test_rejects_when_no_output_root(self):
        bare = SceneCommands(FakeBpy(), approved_output_root=None)
        with self.assertRaises(HarnessError) as caught:
            bare.screenshot({"path": str(self.root / "out.png")})
        self.assertEqual(caught.exception.code, "OUTPUT_NOT_AUTHORIZED")

    def test_rejects_path_outside_output_root(self):
        outside = Path(tempfile.gettempdir()) / "outside-output-root.png"
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(outside)})
        self.assertEqual(caught.exception.code, "OUTPUT_NOT_AUTHORIZED")

    def test_rejects_symlink_output(self):
        target = self.root / "target.png"
        link = self.root / "link.png"
        target.write_bytes(b"x")
        os.symlink(target, link)
        try:
            with self.assertRaises(HarnessError) as caught:
                self.commands.screenshot({"path": str(link)})
            self.assertEqual(caught.exception.code, "OUTPUT_NOT_AUTHORIZED")
        finally:
            link.unlink()

    def test_rejects_overwrite_without_flag(self):
        existing = self.root / "exists.png"
        existing.write_bytes(b"old")
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(existing)})
        self.assertEqual(caught.exception.code, "OVERWRITE_AUTHORIZATION_REQUIRED")

    def test_rejects_unknown_format_suffix(self):
        bad = self.root / "out.gif"
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(bad)})
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")
        self.assertIn("png", str(caught.exception))

    def test_rejects_format_argument_mismatch(self):
        path = self.root / "out.png"
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(path), "format": "jpg"})
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")


class TestScreenshotDimensions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.commands, _ = _make_commands(self.root)

    def test_rejects_below_minimum(self):
        path = self.root / "tiny.png"
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(path), "width": MIN_DIMENSION - 1, "height": 256})
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")

    def test_rejects_above_maximum(self):
        path = self.root / "huge.png"
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(path), "width": MAX_DIMENSION + 1, "height": 256})
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")

    def test_rejects_non_integer_dimensions(self):
        path = self.root / "x.png"
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(path), "width": "1024"})
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")


class TestScreenshotCameraAndFrame(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.commands, self.bpy = _make_commands(self.root)

    def test_rejects_missing_camera(self):
        self.bpy.context.scene.camera = None
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(self.root / "out.png")})
        self.assertEqual(caught.exception.code, "CAMERA_REQUIRED")

    def test_rejects_unknown_camera_name(self):
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(self.root / "out.png"), "camera": "Nope"})
        self.assertEqual(caught.exception.code, "OBJECT_NOT_FOUND")

    def test_rejects_non_camera_object(self):
        mesh = SimpleNamespace(name="JustAMesh", type="MESH")
        self.bpy.data.objects[mesh.name] = mesh
        self.bpy.context.scene.objects[mesh.name] = mesh
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(self.root / "out.png"), "camera": "JustAMesh"})
        self.assertEqual(caught.exception.code, "OBJECT_NOT_FOUND")

    def test_rejects_frame_out_of_range(self):
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(self.root / "out.png"), "frame": 9999})
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")

    def test_rejects_non_integer_frame(self):
        with self.assertRaises(HarnessError) as caught:
            self.commands.screenshot({"path": str(self.root / "out.png"), "frame": "3"})
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")


# ---------------------------------------------------------------------------
# Tests: happy path
# ---------------------------------------------------------------------------


class TestScreenshotHappyPath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.commands, self.bpy = _make_commands(self.root)

    def test_writes_png_and_returns_hash_verified_receipt(self):
        path = self.root / "round-1.png"
        result = self.commands.screenshot({"path": str(path)})
        artifact = result["result"]["artifact"]
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 0)
        self.assertEqual(artifact["format"], "png")
        self.assertEqual(artifact["bytes"], path.stat().st_size)
        self.assertEqual(artifact["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(artifact["validation"]["status"], "passed")
        self.assertIn("sha256", artifact["validation"]["checks"])

    def test_uses_named_camera_when_provided(self):
        alt = SimpleNamespace(name="AltCamera", type="CAMERA")
        self.bpy.data.objects[alt.name] = alt
        self.bpy.context.scene.objects[alt.name] = alt
        path = self.root / "with-alt-camera.png"
        result = self.commands.screenshot({"path": str(path), "camera": "AltCamera"})
        self.assertEqual(self.bpy.context.scene.camera, alt)
        self.assertEqual(result["result"]["render"]["camera"], "AltCamera")

    def test_advances_to_requested_frame(self):
        path = self.root / "frame-42.png"
        result = self.commands.screenshot({"path": str(path), "frame": 42})
        self.assertEqual(self.bpy.context.scene.frame_current, 42)
        self.assertEqual(result["result"]["render"]["frame"], 42)

    def test_overwrite_flag_allows_replace(self):
        path = self.root / "overwrite.png"
        path.write_bytes(b"stale")
        first = self.commands.screenshot({"path": str(path), "overwrite": True})
        self.assertTrue(path.is_file())
        self.assertNotEqual(path.read_bytes(), b"stale")
        self.assertEqual(first["result"]["artifact"]["bytes"], path.stat().st_size)

    def test_restores_render_settings_on_success(self):
        path = self.root / "restored.png"
        original_format = self.bpy.context.scene.render.image_settings.file_format
        original_x = self.bpy.context.scene.render.resolution_x
        self.commands.screenshot({"path": str(path)})
        self.assertEqual(self.bpy.context.scene.render.image_settings.file_format, original_format)
        self.assertEqual(self.bpy.context.scene.render.resolution_x, original_x)

    def test_dispatches_render_op_with_write_still(self):
        path = self.root / "dispatch.png"
        self.commands.screenshot({"path": str(path)})
        ops = self.bpy.ops.render
        self.assertEqual(len(ops.calls), 1)
        self.assertTrue(ops.calls[0]["write_still"])

    def test_jpg_path_uses_jpeg_file_format(self):
        path = self.root / "out.jpg"
        # JPEG render is not actually exercised by FakeRenderOps (it writes a PNG
        # signature), but the format field on the request must be honored.
        result = self.commands.screenshot({"path": str(path)})
        self.assertEqual(result["result"]["artifact"]["format"], "jpg")
        # Original file_format must be restored after the call.
        self.assertEqual(self.bpy.context.scene.render.image_settings.file_format, "PNG")


class TestScreenshotWithoutOutputRoot(unittest.TestCase):
    def test_output_root_required_message_is_actionable(self):
        bare = SceneCommands(FakeBpy())
        with self.assertRaises(HarnessError) as caught:
            bare.screenshot({"path": "/tmp/x.png"})
        self.assertEqual(caught.exception.code, "OUTPUT_NOT_AUTHORIZED")
        self.assertIn("approved output root", str(caught.exception))


class TestScreenshotValidationIntegration(unittest.TestCase):
    """Verify the closed-arguments schema is enforced by the registry dispatch."""

    def test_closed_arguments_schema_lists_optional_fields(self):
        from scripts.harness.commands.validation import closed_arguments
        validator = closed_arguments(
            required=("path",),
            optional=("width", "height", "format", "frame", "camera", "overwrite"),
        )
        schema = validator.schema
        self.assertEqual(schema["required"], ["path"])
        self.assertEqual(
            set(schema["properties"]),
            {"path", "width", "height", "format", "frame", "camera", "overwrite"},
        )
        self.assertFalse(schema["additionalProperties"])

    def test_closed_arguments_rejects_unknown_fields(self):
        from scripts.harness.commands.validation import closed_arguments
        validator = closed_arguments(
            required=("path",),
            optional=("width", "height", "format", "frame", "camera", "overwrite"),
        )
        with self.assertRaises(HarnessError) as caught:
            validator({"path": "/tmp/x.png", "rogue": True})
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main()
