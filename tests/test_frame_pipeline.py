import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.harness.errors import HarnessError
from scripts.harness.frame_pipeline import (
    build_compose_command,
    expected_frames,
    frames_requiring_render,
    inspect_frame_sequence,
    validate_compose_parameters,
    validate_render_parameters,
    write_concat_manifest,
)


class FramePipelineTests(unittest.TestCase):
    def test_render_parameters_are_closed_and_normalized(self):
        result = validate_render_parameters({
            "frameStart": 1,
            "frameEnd": 5,
            "frameStep": 2,
            "width": 1280,
            "height": 720,
            "imageFormat": "PNG",
            "includeAudio": False,
        })
        self.assertEqual(result["frames"], [1, 3, 5])
        self.assertEqual(result["extension"], "png")
        with self.assertRaises(HarnessError):
            validate_render_parameters({"frameStart": 1, "frameEnd": 2, "unknown": True})

    def test_sequence_inspection_distinguishes_complete_missing_and_corrupt_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = root / "frames"
            frames.mkdir()
            first = frames / "frame_000001.png"
            second = frames / "frame_000002.png"
            first.write_bytes(b"one")
            second.write_bytes(b"changed")
            manifest = {
                "receiptVersion": "3.0.0",
                "frameStart": 1,
                "frameEnd": 3,
                "frameStep": 1,
                "format": "PNG",
                "frames": [
                    {"frame": 1, "path": str(first), "bytes": 3,
                     "sha256": "7692c3ad3540bb803c020b3aee66cd8887123234ea0c6e7143c0add73ff431ed"},
                    {"frame": 2, "path": str(second), "bytes": 3,
                     "sha256": "3fc4ccfe745870e2c0d99f71f30ff0656c8d902c3b9f7f688f590a3d21364f0a"},
                ],
            }
            status = inspect_frame_sequence(manifest, root)
            self.assertEqual(status["complete"], [1])
            self.assertEqual(status["corrupt"], [2])
            self.assertEqual(status["missing"], [3])

    def test_compose_parameters_and_command_are_bounded(self):
        parameters = validate_compose_parameters({
            "sourceJobId": "job_frames",
            "codec": "H264",
            "crf": 20,
            "preset": "medium",
        })
        command = build_compose_command(
            Path("/usr/bin/ffmpeg"),
            Path("/approved/frames.ffconcat"),
            Path("/approved/output.mp4"),
            parameters,
            audio_path=Path("/approved/mix.wav"),
            fps=24,
            frame_count=3,
        )
        self.assertIn("libx264", command)
        self.assertIn("-safe", command)
        self.assertIn("-shortest", command)
        self.assertEqual(command[command.index('-r')+1],'24')
        self.assertEqual(command[command.index('-frames:v')+1],'3')
        self.assertNotIn("-filter_complex", command)
        with self.assertRaises(HarnessError):
            validate_compose_parameters({"sourceJobId": "../escape"})

    def test_expected_frames_rejects_invalid_ranges(self):
        self.assertEqual(expected_frames(2, 6, 2), [2, 4, 6])
        for values in ((2, 1, 1), (1, 2, 0), (1.0, 2, 1)):
            with self.subTest(values=values), self.assertRaises(HarnessError):
                expected_frames(*values)

    def test_matching_hash_does_not_hide_an_invalid_png_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'bad.png';path.write_bytes(b'not-a-png')
            manifest={'frameStart':1,'frameEnd':1,'frameStep':1,'format':'PNG','width':1280,'height':720,
              'colorMode':'RGBA','frames':[{'frame':1,'path':str(path),'bytes':path.stat().st_size,
              'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}
            status=inspect_frame_sequence(manifest,root)
            self.assertEqual(status['complete'],[]);self.assertEqual(status['corrupt'],[1])

    def test_resume_selects_only_missing_and_corrupt_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);frames=root/'frames';frames.mkdir()
            good=frames/'frame_000001.png';bad=frames/'frame_000002.png'
            good.write_bytes(b'good');bad.write_bytes(b'bad-now')
            manifest={'frameStart':1,'frameEnd':3,'frameStep':1,'format':'PNG','frames':[
              {'frame':1,'path':str(good),'bytes':4,'sha256':'770e607624d689265ca6c44884d0807d9b054d23c473c106c72be9de08b7376c'},
              {'frame':2,'path':str(bad),'bytes':3,'sha256':'2f05d4b689d270cafb02285f35f44866b7b5f8f6f45f7a4d1c4f704c6c7e4f92'}]}
            self.assertEqual(frames_requiring_render(manifest,root),[2,3])

    def test_concat_manifest_uses_explicit_files_and_frame_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);frames=root/'frames';frames.mkdir();entries=[]
            for frame in (1,3):
                path=frames/f'frame_{frame:06d}.png';path.write_bytes(b'frame')
                entries.append({'frame':frame,'path':str(path),'bytes':5,
                                'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            manifest={'frameStart':1,'frameEnd':3,'frameStep':2,'fps':24,'format':'PNG','frames':entries}
            target=root/'frames.ffconcat';write_concat_manifest(manifest,root,target)
            text=target.read_text()
            self.assertIn('ffconcat version 1.0',text);self.assertEqual(text.count("file '"),3)
            self.assertIn('duration 0.083333333',text)


if __name__ == "__main__":
    unittest.main()
