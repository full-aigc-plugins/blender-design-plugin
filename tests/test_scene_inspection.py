"""Tests for read-only scene inspection bridge.

Covers:
  - Zero / one / multiple cameras
  - Invalid frame ranges
  - Percentage-scaled resolution
  - No materials, colored materials, image textures, unsupported nodes
  - Linked assets outside scope
  - Receipt validates against Task 1 scene_receipt schema
  - Byte-identical receipts across two runs (determinism)
  - Redacted stderr (no absolute paths, no environment dump)
  - Auto-execution stays disabled
  - Read-only inspection (scene state unchanged after)
  - main() entry point emits valid JSON and returns 0 on success
"""

import hashlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

# Ensure scripts/ is importable
_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# Ensure tests/ is importable (for fakes package)
_TESTS_DIR = os.path.dirname(__file__)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from blender_bridge import inspect_scene, main
from validate_document import validate_document
from fakes.fake_bpy import (
    FakeApp,
    FakeBpy,
    FakeCamera,
    FakeContext,
    FakeData,
    FakeLibrary,
    FakeMaterial,
    FakeNode,
    FakeNodeTree,
    FakeObject,
    FakeRenderSettings,
    FakeScene,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_CONTENT = b"BLENDER-fake-content-for-testing"


def _make_project(directory, content=_PROJECT_CONTENT):
    """Create a fake .blend file; return its Path."""
    p = Path(directory) / "project.blend"
    p.write_bytes(content)
    return p


def _expected_fingerprint(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------

def _bpy_no_cameras():
    scene = FakeScene(frame_start=1, frame_end=250)
    data = FakeData(objects=[], materials=[], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


def _bpy_one_camera():
    cam_obj = FakeObject("Camera.Main", obj_type="CAMERA",
                         data=FakeCamera("Camera.Main"))
    scene = FakeScene(frame_start=1, frame_end=250)
    data = FakeData(objects=[cam_obj], materials=[], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


def _bpy_two_cameras():
    c1 = FakeObject("Camera.Main", obj_type="CAMERA",
                    data=FakeCamera("Camera.Main"))
    c2 = FakeObject("Camera.Overhead", obj_type="CAMERA",
                    data=FakeCamera("Camera.Overhead"))
    scene = FakeScene(frame_start=1, frame_end=250)
    data = FakeData(objects=[c1, c2], materials=[], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


def _bpy_invalid_frame_range():
    scene = FakeScene(frame_start=100, frame_end=50)
    data = FakeData(objects=[], materials=[], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


def _bpy_percentage_resolution():
    render = FakeRenderSettings(resolution_x=1920, resolution_y=1080,
                                resolution_percentage=50)
    scene = FakeScene(frame_start=1, frame_end=250, render=render)
    data = FakeData(objects=[], materials=[], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


def _bpy_no_materials():
    scene = FakeScene(frame_start=1, frame_end=250)
    data = FakeData(objects=[], materials=[], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


def _bpy_colored_materials():
    node = FakeNode("Principled BSDF", FakeNode.SHADER)
    tree = FakeNodeTree(nodes=[node])
    mat = FakeMaterial("RedPlastic", use_nodes=True, node_tree=tree)
    obj = FakeObject("Cube", obj_type="MESH", materials=[mat])
    scene = FakeScene(frame_start=1, frame_end=250)
    data = FakeData(objects=[obj], materials=[mat], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


def _bpy_image_textures():
    shader = FakeNode("Principled BSDF", FakeNode.SHADER)
    tex = FakeNode("Image Texture", FakeNode.TEX_IMAGE)
    tree = FakeNodeTree(nodes=[shader, tex])
    mat = FakeMaterial("WoodTex", use_nodes=True, node_tree=tree)
    obj = FakeObject("Table", obj_type="MESH", materials=[mat])
    scene = FakeScene(frame_start=1, frame_end=250)
    data = FakeData(objects=[obj], materials=[mat], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


def _bpy_unsupported_nodes():
    shader = FakeNode("Principled BSDF", FakeNode.SHADER)
    group = FakeNode("CustomGroup", FakeNode.GROUP)
    tree = FakeNodeTree(nodes=[shader, group])
    mat = FakeMaterial("WeirdMat", use_nodes=True, node_tree=tree)
    obj = FakeObject("Suzanne", obj_type="MESH", materials=[mat])
    scene = FakeScene(frame_start=1, frame_end=250)
    data = FakeData(objects=[obj], materials=[mat], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


def _bpy_linked_assets():
    lib = FakeLibrary("/external/models.blend")
    obj = FakeObject("LinkedChair", obj_type="MESH", library=lib)
    scene = FakeScene(frame_start=1, frame_end=250)
    data = FakeData(objects=[obj], materials=[], scenes=[scene])
    return FakeBpy(data=data, context=FakeContext(scene=scene),
                   app=FakeApp("4.2.0"))


# ===========================================================================
# Camera tests
# ===========================================================================

class TestCameras(unittest.TestCase):

    def test_zero_cameras_empty_list_and_warning(self):
        bpy = _bpy_no_cameras()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertEqual(r["cameras"], [])
        self.assertIn("NO_CAMERAS", r["warnings"])

    def test_one_camera(self):
        bpy = _bpy_one_camera()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertEqual(r["cameras"], ["Camera.Main"])

    def test_multiple_cameras(self):
        bpy = _bpy_two_cameras()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertEqual(r["cameras"], ["Camera.Main", "Camera.Overhead"])


# ===========================================================================
# Frame range tests
# ===========================================================================

class TestFrameRange(unittest.TestCase):

    def test_valid_range(self):
        bpy = _bpy_one_camera()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertEqual(r["frameRange"], {"start": 1, "end": 250})
        self.assertNotIn("INVALID_FRAME_RANGE", r["warnings"])

    def test_invalid_range_emits_warning(self):
        bpy = _bpy_invalid_frame_range()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertIn("INVALID_FRAME_RANGE", r["warnings"])
        # Receipt still includes the raw values
        self.assertEqual(r["frameRange"], {"start": 100, "end": 50})


# ===========================================================================
# Resolution tests
# ===========================================================================

class TestResolution(unittest.TestCase):

    def test_full_resolution(self):
        bpy = _bpy_one_camera()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertEqual(r["resolution"], {"width": 1920, "height": 1080})

    def test_percentage_scaled(self):
        bpy = _bpy_percentage_resolution()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertEqual(r["resolution"], {"width": 960, "height": 540})


# ===========================================================================
# Material / preview-mode tests
# ===========================================================================

class TestMaterialsAndPreviewModes(unittest.TestCase):

    def test_no_materials_white_model_only(self):
        bpy = _bpy_no_materials()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertEqual(r["previewModes"], ["white_model"])

    def test_colored_materials_adds_material_preview(self):
        bpy = _bpy_colored_materials()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertIn("white_model", r["previewModes"])
        self.assertIn("material_preview", r["previewModes"])

    def test_image_textures_adds_textured(self):
        bpy = _bpy_image_textures()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertIn("textured", r["previewModes"])


# ===========================================================================
# Warning tests
# ===========================================================================

class TestWarnings(unittest.TestCase):

    def test_unsupported_nodes_warning(self):
        bpy = _bpy_unsupported_nodes()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertIn("UNSUPPORTED_NODES", r["warnings"])

    def test_linked_assets_warning(self):
        bpy = _bpy_linked_assets()
        with tempfile.TemporaryDirectory() as td:
            r = inspect_scene(bpy, _make_project(td))
        self.assertIn("LINKED_ASSETS_OUTSIDE_SCOPE", r["warnings"])


# ===========================================================================
# Schema contract (Task 1 cross-validation)
# ===========================================================================

class TestSchemaContract(unittest.TestCase):
    """Receipts must satisfy the Task 1 scene_receipt schema."""

    def _assert_valid(self, receipt):
        errors = validate_document("scene_receipt", receipt)
        self.assertEqual(errors, [], f"Schema validation failed: {errors}")

    def test_minimal_scene(self):
        bpy = _bpy_one_camera()
        with tempfile.TemporaryDirectory() as td:
            self._assert_valid(inspect_scene(bpy, _make_project(td)))

    def test_complex_scene(self):
        bpy = _bpy_image_textures()
        with tempfile.TemporaryDirectory() as td:
            self._assert_valid(inspect_scene(bpy, _make_project(td)))

    def test_no_cameras(self):
        bpy = _bpy_no_cameras()
        with tempfile.TemporaryDirectory() as td:
            self._assert_valid(inspect_scene(bpy, _make_project(td)))

    def test_linked_assets(self):
        bpy = _bpy_linked_assets()
        with tempfile.TemporaryDirectory() as td:
            self._assert_valid(inspect_scene(bpy, _make_project(td)))


# ===========================================================================
# Determinism
# ===========================================================================

class TestDeterminism(unittest.TestCase):

    def test_byte_identical_json_across_two_runs(self):
        """Same fixture must yield byte-identical JSON stdout twice."""
        bpy = _bpy_one_camera()
        content = b"BLENDER-determinism-probe"
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(td, content=content)
            request_path = Path(td) / "req.json"
            request_path.write_text(json.dumps({"projectPath": str(project)}))

            outputs = []
            for _ in range(2):
                buf = io.StringIO()
                with patch.dict(sys.modules, {"bpy": bpy}):
                    with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                        main(str(request_path))
                outputs.append(buf.getvalue())

        self.assertEqual(outputs[0], outputs[1],
                         "stdout was not byte-identical across two runs")

    def test_fingerprint_deterministic(self):
        """Same file content produces identical fingerprint."""
        bpy = _bpy_one_camera()
        content = b"BLENDER-fingerprint-probe"
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(td, content=content)
            r1 = inspect_scene(bpy, project)
            r2 = inspect_scene(bpy, project)
        self.assertEqual(r1["projectFingerprint"], r2["projectFingerprint"])


# ===========================================================================
# Redaction
# ===========================================================================

class TestRedaction(unittest.TestCase):
    """Stderr must not leak absolute paths or environment variables."""

    def _run_main(self, bpy, content=b"BLENDER-redaction-probe"):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(td, content=content)
            request_path = Path(td) / "req.json"
            request_path.write_text(json.dumps({"projectPath": str(project)}))

            out_buf, err_buf = io.StringIO(), io.StringIO()
            with patch.dict(sys.modules, {"bpy": bpy}):
                with redirect_stdout(out_buf), redirect_stderr(err_buf):
                    main(str(request_path))
        return out_buf.getvalue(), err_buf.getvalue()

    def test_no_absolute_paths_on_stderr(self):
        _, stderr = self._run_main(_bpy_one_camera())
        abs_pat = re.compile(r"/(?:Users|home|tmp|var|etc)/\S+")
        self.assertIsNone(abs_pat.search(stderr),
                         f"Stderr leaked absolute path: {stderr}")

    def test_no_environment_on_stderr(self):
        _, stderr = self._run_main(_bpy_one_camera())
        for marker in ("PATH=", "HOME=", "TMPDIR="):
            self.assertNotIn(marker, stderr,
                           f"Stderr leaked env var ({marker}): {stderr}")


# ===========================================================================
# Auto-execution
# ===========================================================================

class TestAutoExecutionDisabled(unittest.TestCase):

    def test_auto_exec_stays_false(self):
        bpy = _bpy_one_camera()
        self.assertFalse(
            bpy.context.preferences.filepaths.use_scripts_auto_execute,
            "Auto-execution must be disabled by default",
        )


# ===========================================================================
# Read-only (no scene mutation)
# ===========================================================================

class TestReadOnly(unittest.TestCase):
    """inspect_scene must not mutate any observable scene state."""

    def _assert_unchanged(self, bpy):
        before = bpy.snapshot()
        with tempfile.TemporaryDirectory() as td:
            inspect_scene(bpy, _make_project(td))
        self.assertEqual(before, bpy.snapshot(),
                         "Scene state was mutated during inspection")

    def test_empty_scene_unchanged(self):
        self._assert_unchanged(_bpy_no_cameras())

    def test_material_scene_unchanged(self):
        self._assert_unchanged(_bpy_colored_materials())

    def test_linked_scene_unchanged(self):
        self._assert_unchanged(_bpy_linked_assets())


# ===========================================================================
# main() entry point
# ===========================================================================

class TestMainEntryPoint(unittest.TestCase):

    def _run_main(self, bpy, content=_PROJECT_CONTENT):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(td, content=content)
            request_path = Path(td) / "req.json"
            request_path.write_text(json.dumps({"projectPath": str(project)}))

            out_buf, err_buf = io.StringIO(), io.StringIO()
            with patch.dict(sys.modules, {"bpy": bpy}):
                with redirect_stdout(out_buf), redirect_stderr(err_buf):
                    rc = main(str(request_path))
        return rc, out_buf.getvalue(), err_buf.getvalue()

    def test_returns_zero(self):
        rc, _, _ = self._run_main(_bpy_one_camera())
        self.assertEqual(rc, 0)

    def test_emits_single_json_document(self):
        _, stdout, _ = self._run_main(_bpy_one_camera())
        receipt = json.loads(stdout)
        self.assertEqual(receipt["schemaVersion"], "codex-blender.receipt/v1")

    def test_stdout_validates_schema(self):
        _, stdout, _ = self._run_main(_bpy_one_camera())
        receipt = json.loads(stdout)
        errors = validate_document("scene_receipt", receipt)
        self.assertEqual(errors, [], f"main() output failed schema: {errors}")


if __name__ == "__main__":
    unittest.main()
