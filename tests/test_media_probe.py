"""Tests for media_probe: ffprobe discovery, probing, and validation."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
for _d in (_SCRIPTS_DIR, _REPO_ROOT):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from media_probe import discover_ffprobe, probe_media, validate_media, ProbeError


def _write_fake_ffprobe(directory, exit_code=0, stdout="", stderr=""):
    """Create a stub ffprobe executable that returns the given output."""
    script = os.path.join(directory, "ffprobe")
    with open(script, "w") as f:
        f.write("#!/bin/sh\n")
        f.write(f"echo '{stdout}'\n")
        f.write(f"exit {exit_code}\n")
    os.chmod(script, 0o755)
    return script


def _sample_ffprobe_output(codec="h264", width=1280, height=720, fps="24/1",
                            duration="10.5"):
    return json.dumps({
        "streams": [{
            "codec_type": "video",
            "codec_name": codec,
            "width": width,
            "height": height,
            "r_frame_rate": fps,
            "avg_frame_rate": fps,
        }],
        "format": {
            "duration": duration,
            "size": "102400",
        },
    })


def _write_test_video(directory, size=102400, name="test.mp4"):
    path = os.path.join(directory, name)
    with open(path, "wb") as f:
        f.write(b"\x00" * size)
    return path


class TestDiscoverFfprobe(unittest.TestCase):
    def test_explicit_path_used(self):
        with tempfile.TemporaryDirectory() as td:
            ffprobe = _write_fake_ffprobe(td)
            result = discover_ffprobe(ffprobe)
            self.assertEqual(result, ffprobe)

    def test_env_variable_used(self):
        with tempfile.TemporaryDirectory() as td:
            ffprobe = _write_fake_ffprobe(td)
            with mock.patch.dict(os.environ, {"JIMENG_FFPROBE": ffprobe}):
                result = discover_ffprobe()
            self.assertEqual(result, ffprobe)

    def test_missing_returns_none(self):
        result = discover_ffprobe("/nonexistent/ffprobe")
        # Should return None if no other candidate works
        # (unless ffprobe is installed on the system)
        if shutil.which("ffprobe"):
            self.assertIsNotNone(result)
        else:
            self.assertIsNone(result)


class TestProbeMedia(unittest.TestCase):
    def test_valid_h264_file(self):
        with tempfile.TemporaryDirectory() as td:
            video = _write_test_video(td)
            ffprobe = _write_fake_ffprobe(td, stdout=_sample_ffprobe_output())
            result = probe_media(video, ffprobe)
            self.assertEqual(result["codec"], "h264")
            self.assertEqual(result["width"], 1280)
            self.assertEqual(result["height"], 720)
            self.assertAlmostEqual(result["fps"], 24.0, places=1)
            self.assertAlmostEqual(result["durationSeconds"], 10.5, places=1)
            self.assertEqual(result["bytes"], 102400)
            self.assertEqual(len(result["sha256"]), 64)

    def test_missing_ffprobe_raises_dependency_missing(self):
        with tempfile.TemporaryDirectory() as td:
            video = _write_test_video(td)
            with mock.patch("media_probe.discover_ffprobe", return_value=None):
                with self.assertRaises(ProbeError) as ctx:
                    probe_media(video)
            self.assertEqual(ctx.exception.category, "DEPENDENCY_MISSING")

    def test_nonexistent_file_raises(self):
        with self.assertRaises(ProbeError) as ctx:
            probe_media("/nonexistent.mp4", "/bin/false")
        self.assertEqual(ctx.exception.category, "MEDIA_INVALID")

    def test_empty_file_raises(self):
        with tempfile.TemporaryDirectory() as td:
            video = _write_test_video(td, size=0)
            with self.assertRaises(ProbeError) as ctx:
                probe_media(video, "/bin/false")
            self.assertEqual(ctx.exception.category, "MEDIA_INVALID")

    def test_ffprobe_timeout_raises(self):
        with tempfile.TemporaryDirectory() as td:
            video = _write_test_video(td)
            with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 30)):
                with self.assertRaises(ProbeError) as ctx:
                    probe_media(video, "/usr/bin/ffprobe")
            self.assertEqual(ctx.exception.category, "MEDIA_INVALID")

    def test_no_video_stream_raises(self):
        with tempfile.TemporaryDirectory() as td:
            video = _write_test_video(td)
            ffprobe = _write_fake_ffprobe(td, stdout=json.dumps({
                "streams": [{"codec_type": "audio"}],
                "format": {"duration": "10", "size": "1024"},
            }))
            with self.assertRaises(ProbeError) as ctx:
                probe_media(video, ffprobe)
            self.assertEqual(ctx.exception.category, "MEDIA_INVALID")


class TestValidateMedia(unittest.TestCase):
    def _probe(self, codec="h264", width=1280, height=720, fps=24.0,
               duration=10.5, file_bytes=102400):
        return {
            "codec": codec, "width": width, "height": height,
            "fps": fps, "durationSeconds": duration, "bytes": file_bytes,
            "sha256": "a" * 64,
        }

    def _profile(self, fps=24, duration=30, file_size=209715200):
        return {"fps": fps, "duration": duration, "file_size": file_size}

    def test_valid_probe_passes(self):
        errors = validate_media(self._probe(), self._profile())
        self.assertEqual(errors, [])

    def test_wrong_codec_fails(self):
        errors = validate_media(self._probe(codec="vp9"), self._profile())
        self.assertTrue(any("codec" in e for e in errors))

    def test_odd_dimensions_fail(self):
        errors = validate_media(self._probe(width=1281, height=720), self._profile())
        self.assertTrue(any("odd" in e for e in errors))

    def test_zero_dimensions_fail(self):
        errors = validate_media(self._probe(width=0), self._profile())
        self.assertTrue(any("invalid" in e for e in errors))

    def test_fps_mismatch_fails(self):
        errors = validate_media(self._probe(fps=30.0), self._profile(fps=24))
        self.assertTrue(any("fps" in e for e in errors))

    def test_duration_exceeds_limit_fails(self):
        errors = validate_media(self._probe(duration=60.0), self._profile(duration=30))
        self.assertTrue(any("duration" in e for e in errors))

    def test_file_too_large_fails(self):
        errors = validate_media(
            self._probe(file_bytes=300 * 1024 * 1024),
            self._profile(file_size=200 * 1024 * 1024),
        )
        self.assertTrue(any("large" in e for e in errors))

    def test_mp4_codec_aliases_accepted(self):
        for alias in ("h264", "h.264", "avc", "avc1", "libx264"):
            errors = validate_media(self._probe(codec=alias), self._profile())
            self.assertEqual(errors, [], f"codec alias {alias} should be accepted")


if __name__ == "__main__":
    unittest.main()
