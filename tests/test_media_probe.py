import json
import subprocess
import unittest
from pathlib import Path

from scripts.harness.errors import HarnessError
from scripts.harness.media_probe import probe_video


class TestMediaProbe(unittest.TestCase):
    def test_parses_h264_video_stream(self):
        payload = {"streams": [{"codec_name": "h264", "width": 1280, "height": 720, "avg_frame_rate": "24/1"}], "format": {"duration": "2.5"}}
        runner = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, json.dumps(payload), "")
        result = probe_video(Path("/tmp/test.mp4"), Path("/app/ffprobe"), runner=runner)
        self.assertEqual(result, {"codec": "h264", "width": 1280, "height": 720, "fps": 24.0, "duration_seconds": 2.5})

    def test_rejects_missing_video_stream(self):
        runner = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, '{"streams":[],"format":{}}', "")
        with self.assertRaises(HarnessError) as caught:
            probe_video(Path("/tmp/test.mp4"), Path("/app/ffprobe"), runner=runner)
        self.assertEqual(caught.exception.code, "MEDIA_INVALID")

    def test_rejects_probe_failure(self):
        runner = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "bad media")
        with self.assertRaises(HarnessError):
            probe_video(Path("/tmp/test.mp4"), Path("/app/ffprobe"), runner=runner)


if __name__ == "__main__":
    unittest.main()
