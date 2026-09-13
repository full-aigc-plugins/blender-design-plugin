"""Contract tests for the preview-only Dreamina 3D Blender adapter."""

from __future__ import annotations

import os
import json
import sys
import tempfile
import subprocess
import shutil
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "bin" / "blender_adapter"
PREVIEW_BRIDGE = ROOT / "scripts" / "preview_only_bridge.py"
MEDIA_PROBE = ROOT / "scripts" / "media_probe.py"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import blender_adapter
import media_probe
import preview_only_bridge
from tests.test_codex_integration import _install_fake_bpy, _make_scene


class AdapterDistributionTests(unittest.TestCase):
    def test_adapter_is_shipped_as_an_executable(self) -> None:
        self.assertTrue(ADAPTER.is_file(), "bin/blender_adapter must be shipped")
        self.assertTrue(os.access(ADAPTER, os.X_OK), "bin/blender_adapter must be executable")

    def test_preview_bridge_and_media_probe_are_shipped(self) -> None:
        self.assertTrue(PREVIEW_BRIDGE.is_file(), "preview-only Blender bridge must be shipped")
        self.assertTrue(MEDIA_PROBE.is_file(), "ffprobe-backed media validation must be shipped")


class AdapterCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.scene = self.root / "scene.blend"
        self.scene.write_bytes(b"BLENDER")
        self.request = self.root / "request.json"
        self.receipt = self.root / "receipt.json"
        self.output = self.root / "preview.mp4"

    def _write_request(self, **updates: object) -> None:
        payload = {
            "scene": str(self.scene),
            "camera_name": "Camera",
            "frame_range": {"start": 1, "end": 48},
            "artifact_id": "artifact-1",
            "output_label": "preview",
        }
        payload.update(updates)
        self.request.write_text(json.dumps(payload), encoding="utf-8")

    def test_inspect_writes_the_returned_receipt_atomically(self) -> None:
        self._write_request()
        expected = {"status": "inspect_ok", "scene": str(self.scene)}
        with mock.patch.object(blender_adapter, "_run_blender_request", return_value=expected, create=True) as run:
            code = blender_adapter.main([
                "--request", str(self.request),
                "--receipt", str(self.receipt),
                "--output", str(self.output),
                "--inspect",
            ])
        self.assertEqual(code, 0)
        self.assertTrue(self.receipt.is_file(), "inspect must publish a receipt")
        self.assertEqual(json.loads(self.receipt.read_text()), expected)
        self.assertEqual(run.call_args.kwargs["mode"], "inspect")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_export_runner_uses_preview_only_bridge_and_builds_shared_receipt(self) -> None:
        self._write_request(blender_executable="/Applications/Blender.app/Contents/MacOS/Blender")
        generated = self.root / "generated.mp4"
        generated.write_bytes(b"real-video-placeholder")
        child_result = {
            "rendered_path": str(generated),
            "camera": "Camera",
            "frame_range": {"start": 1, "end": 48},
            "preview_kind": "white_model",
            "restoration": {"status": "confirmed", "evidence": "state restored"},
        }
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="Blender log\n" + json.dumps(child_result) + "\nBlender quit\n",
            stderr="",
        )
        metadata = {
            "codec": "h264", "container": "mp4",
            "dimensions": {"width": 1280, "height": 720},
            "fps": 24.0, "duration_seconds": 2.0,
            "bytes": len(b"real-video-placeholder"), "sha256": "b" * 64,
        }
        runtime = mock.Mock(
            executable=Path("/Applications/Blender.app/Contents/MacOS/Blender"),
            version="5.2.1",
        )
        request = json.loads(self.request.read_text())
        with mock.patch.object(blender_adapter, "discover_blender", return_value=runtime, create=True), \
             mock.patch.object(blender_adapter, "build_argv", return_value=["blender"], create=True) as build, \
             mock.patch.object(blender_adapter, "run_blender", return_value=completed, create=True), \
             mock.patch.object(blender_adapter, "probe_media", return_value=metadata, create=True):
            try:
                receipt = blender_adapter._run_blender_request(
                    request,
                    request_path=self.request,
                    output_path=self.output,
                    mode="export",
                )
            except blender_adapter.AdapterError as exc:
                self.fail(f"export runner must be implemented: {exc}")
        self.assertEqual(build.call_args.kwargs["bridge_path"].name, "preview_only_bridge.py")
        self.assertEqual(receipt["schema_version"], "1.0.0")
        self.assertEqual(receipt["producer_plugin"], "codex-blender")
        self.assertEqual(receipt["path"], str(self.output.resolve()))
        self.assertEqual(receipt["sha256"], "b" * 64)
        self.assertEqual(self.output.read_bytes(), b"real-video-placeholder")

    def test_status_reads_existing_receipt_without_running_blender(self) -> None:
        existing = {"status": "completed", "artifact_id": "artifact-1"}
        self.receipt.write_text(json.dumps(existing), encoding="utf-8")
        with mock.patch.object(blender_adapter, "_run_blender_request", create=True) as run:
            with mock.patch("sys.stdout") as stdout:
                code = blender_adapter.main([
                    "--status", "--request", str(self.request), "--receipt", str(self.receipt),
                ])
        self.assertEqual(code, 0)
        run.assert_not_called()
        self.assertIn("completed", "".join(call.args[0] for call in stdout.write.call_args_list))

    def test_export_rejects_missing_output_before_running_blender(self) -> None:
        self._write_request()
        with mock.patch.object(blender_adapter, "_run_blender_request", create=True) as run:
            code = blender_adapter.main([
                "--request", str(self.request), "--receipt", str(self.receipt),
            ])
        self.assertEqual(code, 2)
        run.assert_not_called()
        self.assertFalse(self.receipt.exists())

    def test_export_rejects_a_symlinked_output_before_running_blender(self) -> None:
        self._write_request()
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"do-not-overwrite")
        self.output.symlink_to(outside)
        with mock.patch.object(blender_adapter, "_run_blender_request", create=True) as run:
            code = blender_adapter.main([
                "--request", str(self.request),
                "--receipt", str(self.receipt),
                "--output", str(self.output),
            ])
        self.assertEqual(code, 2)
        run.assert_not_called()
        self.assertEqual(outside.read_bytes(), b"do-not-overwrite")

    def test_export_publishes_only_a_confirmed_shared_receipt(self) -> None:
        self._write_request()
        expected = {
            "schema_version": "1.0.0",
            "producer_plugin": "codex-blender",
            "producer_version": "0.1.0",
            "artifact_id": "artifact-1",
            "path": str(self.output),
            "sha256": "a" * 64,
            "codec": "h264",
            "container": "mp4",
            "dimensions": {"width": 1280, "height": 720},
            "fps": 24.0,
            "duration_seconds": 2.0,
            "bytes": 4096,
            "camera": {"name": "Camera"},
            "frame_range": {"start": 1, "end": 48},
            "preview_mode": "camera_render",
            "restoration": {"status": "confirmed", "evidence": "state restored"},
        }
        with mock.patch.object(blender_adapter, "_run_blender_request", return_value=expected, create=True):
            code = blender_adapter.main([
                "--request", str(self.request),
                "--receipt", str(self.receipt),
                "--output", str(self.output),
            ])
        self.assertEqual(code, 0)
        self.assertTrue(self.receipt.is_file(), "export must publish a receipt")
        self.assertEqual(json.loads(self.receipt.read_text()), expected)


class PreviewOnlyBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.scene = _make_scene(frame_start=1, frame_end=48)
        self.bpy = _install_fake_bpy(self.scene)

    def test_bridge_bootstraps_repo_import_paths_when_blender_runs_it_directly(self) -> None:
        scripts_path = str(ROOT / "scripts")
        root_path = str(ROOT)
        original = list(sys.path)
        self.addCleanup(lambda: setattr(sys, "path", original))
        sys.path[:] = [entry for entry in sys.path if entry not in {scripts_path, root_path}]
        bootstrap = getattr(preview_only_bridge, "_bootstrap_import_paths", None)
        self.assertIsNotNone(bootstrap, "direct Blender execution needs an import-path bootstrap")
        bootstrap()
        self.assertIn(scripts_path, sys.path)
        self.assertIn(root_path, sys.path)

    def test_renders_locally_and_never_starts_the_upload_bridge(self) -> None:
        self.assertTrue(
            hasattr(preview_only_bridge, "render_preview_only"),
            "preview-only bridge must expose render_preview_only",
        )
        generated = self.root / "generated.mp4"

        def render_movie(_scene: object, _config: object) -> str:
            generated.write_bytes(b"preview")
            return str(generated)

        request = {
            "camera_name": "MainCam",
            "frame_range": {"start": 1, "end": 48},
            "output_path": str(self.root / "requested.mp4"),
            "resolution": "720p",
        }
        with mock.patch(
            "vendor.jimeng_blender_uploader.upload_bridge.start_local_bridge",
            side_effect=AssertionError("preview-only mode must not upload"),
        ) as upload:
            result = preview_only_bridge.render_preview_only(
                self.bpy, request, render_movie=render_movie,
            )
        upload.assert_not_called()
        self.assertEqual(Path(result["rendered_path"]), generated.resolve())
        self.assertEqual(result["camera"], "MainCam")
        self.assertEqual(result["frame_range"], {"start": 1, "end": 48})
        self.assertEqual(result["restoration"]["status"], "confirmed")

    def test_background_renderer_uses_standard_render_and_restores_scene(self) -> None:
        renderer = getattr(preview_only_bridge, "render_background_movie", None)
        self.assertIsNotNone(renderer, "background Workbench renderer must exist")
        original = self.scene.snapshot()
        rendered_frames: list[Path] = []

        def render_still(**kwargs: object) -> None:
            self.assertEqual(kwargs, {"write_still": True})
            frame = Path(self.scene.render.filepath)
            frame.write_bytes(b"png")
            rendered_frames.append(frame)

        self.bpy.ops.render.render = mock.Mock(side_effect=render_still)
        output = self.root / "preview.mp4"

        def encode(frames_dir: str, output_path: str, fps: int, start: int) -> str:
            self.assertEqual(fps, 24)
            self.assertEqual(start, 1)
            self.assertEqual(len(list(Path(frames_dir).glob("frame_*.png"))), 48)
            Path(output_path).write_bytes(b"mp4")
            return output_path

        result = renderer(self.bpy, self.scene, output, encode_sequence=encode)
        self.assertEqual(Path(result), output.resolve())
        self.assertEqual(len(rendered_frames), 48)
        self.assertEqual(self.scene.snapshot(), original)
        self.assertFalse(output.with_suffix("").with_name("preview_frames").exists())


class MediaProbeTests(unittest.TestCase):
    def test_probes_real_h264_mp4_and_hashes_the_final_bytes(self) -> None:
        self.assertTrue(hasattr(media_probe, "probe_media"), "media probe API must exist")
        with tempfile.TemporaryDirectory() as raw:
            video = Path(raw) / "fixture.mp4"
            ffmpeg = shutil.which("ffmpeg")
            self.assertIsNotNone(ffmpeg, "ffmpeg is required for media contract tests")
            subprocess.run(
                [
                    ffmpeg, "-y", "-f", "lavfi",
                    "-i", "color=c=black:s=320x180:r=24:d=0.5",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
                ],
                check=True, capture_output=True,
            )
            result = media_probe.probe_media(video)
        self.assertEqual(result["codec"], "h264")
        self.assertEqual(result["container"], "mp4")
        self.assertEqual(result["dimensions"], {"width": 320, "height": 180})
        self.assertEqual(result["fps"], 24.0)
        self.assertGreater(result["duration_seconds"], 0.1)
        self.assertRegex(result["sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
