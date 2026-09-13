import unittest
import subprocess
import sys
from pathlib import Path

from scripts.dreamina_adapter import build_preview_receipt, export_preview


class TestPreviewHandoffReceipt(unittest.TestCase):
    def test_adapter_help_runs_as_script(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "dreamina_adapter.py"
        result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_builds_orchestrator_contract_from_verified_artifact(self):
        artifact = {"path": "/tmp/preview.mp4", "sha256": "a" * 64, "bytes": 1000}
        request = {
            "artifact_id": "blender_preview_1",
            "camera_name": "HeroCamera",
            "frame_range": {"start": 1, "end": 48},
        }
        media = {"codec": "h264", "width": 1280, "height": 720, "fps": 24.0, "duration_seconds": 2.0}
        receipt = build_preview_receipt(artifact, request, media)
        self.assertEqual(receipt["producer_plugin"], "codex-blender")
        self.assertEqual(receipt["artifact_id"], "blender_preview_1")
        self.assertEqual(receipt["dimensions"], {"width": 1280, "height": 720})
        self.assertEqual(receipt["restoration"]["status"], "confirmed")

    def test_rejects_non_h264_media(self):
        with self.assertRaises(ValueError):
            build_preview_receipt(
                {"path": "/tmp/x.mp4", "sha256": "a" * 64, "bytes": 1},
                {"artifact_id": "abc", "camera_name": "Camera", "frame_range": {"start": 1, "end": 2}},
                {"codec": "hevc", "width": 10, "height": 10, "fps": 24, "duration_seconds": 1},
            )

    def test_export_preview_runs_commit_authorize_export_sequence(self):
        calls = []
        def send(command, arguments, **kwargs):
            calls.append((command, arguments, kwargs))
            if command == "transaction.commit":
                return {"status": "succeeded", "snapshotId": "snap-1"}
            if command == "session.authorize":
                return {"status": "succeeded", "result": {"authorization": "claim"}}
            if command == "export.file":
                return {"status": "succeeded", "result": {"artifact": {"path": "/tmp/out.mp4", "sha256": "a" * 64, "bytes": 10}}}
            return {"status": "succeeded"}
        receipt = export_preview(
            {"artifact_id": "preview_1", "camera_name": "Camera", "frame_range": {"start": 1, "end": 48}},
            output_path="/tmp/out.mp4",
            send=send,
            probe=lambda _path: {"codec": "h264", "width": 1280, "height": 720, "fps": 24, "duration_seconds": 2},
        )
        self.assertEqual([call[0] for call in calls], ["transaction.begin", "transaction.commit", "session.authorize", "export.file"])
        self.assertEqual(receipt["artifact_id"], "preview_1")


if __name__ == "__main__":
    unittest.main()
