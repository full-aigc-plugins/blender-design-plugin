import unittest

from scripts.dreamina_adapter import build_preview_receipt


class TestPreviewHandoffReceipt(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
