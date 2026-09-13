import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.harness.snapshot import BlenderCheckpointStore


class TestBlenderCheckpointStore(unittest.TestCase):
    def test_capture_and_restore_verify_scene_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            state = {"objects": [SimpleNamespace(name="A", type="MESH", location=(0, 0, 0), rotation_euler=(0, 0, 0), scale=(1, 1, 1))]}
            saved = {}

            def save_as_mainfile(filepath, copy, check_existing):
                Path(filepath).write_bytes(b"blend")
                saved[filepath] = [item.name for item in state["objects"]]

            def open_mainfile(filepath):
                state["objects"] = [SimpleNamespace(name=name, type="MESH", location=(0, 0, 0), rotation_euler=(0, 0, 0), scale=(1, 1, 1)) for name in saved[filepath]]
                bpy.data.objects = state["objects"]

            bpy = SimpleNamespace(
                data=SimpleNamespace(objects=state["objects"]),
                context=SimpleNamespace(scene=SimpleNamespace(frame_start=1, frame_end=10, camera=None)),
                ops=SimpleNamespace(wm=SimpleNamespace(save_as_mainfile=save_as_mainfile, open_mainfile=open_mainfile)),
            )
            store = BlenderCheckpointStore(bpy, Path(directory))
            snapshot = store.capture()
            state["objects"].append(SimpleNamespace(name="B", type="MESH", location=(0, 0, 0), rotation_euler=(0, 0, 0), scale=(1, 1, 1)))
            bpy.data.objects = state["objects"]
            restored = store.restore(snapshot)
            self.assertTrue(restored)
            self.assertEqual([item.name for item in bpy.data.objects], ["A"])


if __name__ == "__main__":
    unittest.main()
