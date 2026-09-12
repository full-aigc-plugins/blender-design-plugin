import tempfile
import unittest
from pathlib import Path

from scripts.harness.artifact_validator import artifact_receipt, sha256_file
from scripts.harness.errors import HarnessError
from scripts.harness.exporter import Exporter


class FakeBpy:
    def __init__(self):
        self.calls = []
        self.ops = type("Ops", (), {})()
        self.ops.wm = type("Wm", (), {})()
        self.ops.export_scene = type("ExportScene", (), {})()
        self.ops.wm.save_as_mainfile = lambda **kwargs: self._write("blend", kwargs)
        self.ops.export_scene.gltf = lambda **kwargs: self._write("gltf", kwargs)
        self.ops.export_scene.fbx = lambda **kwargs: self._write("fbx", kwargs)
        self.ops.wm.obj_export = lambda **kwargs: self._write("obj", kwargs)
        self.ops.wm.stl_export = lambda **kwargs: self._write("stl", kwargs)
        image_settings = type("ImageSettings", (), {"file_format": "PNG"})()
        ffmpeg = type("Ffmpeg", (), {"format": "MPEG4", "codec": "H264", "constant_rate_factor": "MEDIUM"})()
        render = type("Render", (), {"filepath": "", "image_settings": image_settings, "ffmpeg": ffmpeg, "engine": "BLENDER_EEVEE_NEXT"})()
        self.context = type("Context", (), {"scene": type("Scene", (), {"render": render, "frame_start": 1, "frame_end": 2})()})()
        self.ops.render = type("RenderOps", (), {})()
        self.ops.render.render = self._render

    def _write(self, kind, kwargs):
        self.calls.append((kind, kwargs))
        Path(kwargs["filepath"]).write_bytes(kind.encode())

    def _render(self, write_still=False, animation=False):
        self.calls.append(("render", {"write_still": write_still, "animation": animation}))
        if animation:
            prefix = Path(self.context.scene.render.filepath)
            for frame in range(self.context.scene.frame_start, self.context.scene.frame_end + 1):
                Path(str(prefix) + f"{frame:04d}.png").write_bytes(b"frame")
        else:
            Path(self.context.scene.render.filepath).write_bytes(b"media")


class TestArtifactValidator(unittest.TestCase):
    def test_receipt_hashes_real_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.glb"
            path.write_bytes(b"glb")
            receipt = artifact_receipt(path, format_name="glb", session_id="s1", scene_revision=3, snapshot_id="snap-3")
            self.assertEqual(receipt["sha256"], sha256_file(path))
            self.assertEqual(receipt["validation"]["status"], "passed")


class TestExporter(unittest.TestCase):
    def test_model_format_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bpy = FakeBpy()
            exporter = Exporter(bpy, approved_output_root=root)
            for extension in ("blend", "glb", "gltf", "fbx", "obj", "stl"):
                receipt = exporter.export(root / f"asset.{extension}", session_id="s1", scene_revision=1, snapshot_id="snap-1")
                self.assertEqual(receipt["format"], extension)
                self.assertTrue(Path(receipt["path"]).is_file())

    def test_image_and_video_format_routes_restore_render_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bpy = FakeBpy()
            exporter = Exporter(
                bpy,
                approved_output_root=root,
                encode_runner=lambda _pattern, target, _fps, _start: Path(target).write_bytes(b"mp4"),
            )
            before = (bpy.context.scene.render.filepath, bpy.context.scene.render.image_settings.file_format)
            for extension in ("png", "jpg", "mp4"):
                receipt = exporter.export(root / f"preview.{extension}", session_id="s1", scene_revision=1, snapshot_id="snap-1")
                self.assertEqual(receipt["format"], extension)
            after = (bpy.context.scene.render.filepath, bpy.context.scene.render.image_settings.file_format)
            self.assertEqual(after, before)

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            exporter = Exporter(FakeBpy(), approved_output_root=Path(directory) / "approved")
            with self.assertRaises(HarnessError) as caught:
                exporter.export(Path(directory) / "outside.glb", session_id="s1", scene_revision=1, snapshot_id="snap-1")
            self.assertEqual(caught.exception.code, "OUTPUT_NOT_AUTHORIZED")

    def test_existing_file_requires_overwrite_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "asset.glb"
            path.write_bytes(b"old")
            exporter = Exporter(FakeBpy(), approved_output_root=root)
            with self.assertRaises(HarnessError) as caught:
                exporter.export(path, session_id="s1", scene_revision=1, snapshot_id="snap-1")
            self.assertEqual(caught.exception.code, "OVERWRITE_AUTHORIZATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
