import tempfile
import unittest
import zipfile
from pathlib import Path

from connector.codex_blender_connector import runtime
from scripts.package_connector import package_connector


class TestConnectorRuntime(unittest.TestCase):
    def tearDown(self):
        runtime.stop()

    def test_not_started_on_import(self):
        self.assertFalse(runtime.is_running())

    def test_start_and_revoke_use_shared_harness(self):
        events = []

        class Handle:
            descriptor_path = Path("/tmp/session.json")
            def close(self):
                events.append("closed")

        handle = runtime.start(
            object(),
            session_id="s1",
            runtime_dir=Path("/tmp"),
            start_function=lambda *_args, **_kwargs: Handle(),
        )
        self.assertTrue(runtime.is_running())
        self.assertIs(handle, runtime.current())
        runtime.stop()
        self.assertEqual(events, ["closed"])

    def test_file_load_revokes_active_connector(self):
        events = []
        class Handle:
            descriptor_path = Path("/tmp/session.json")
            def close(self):
                events.append("closed")
        runtime.start(object(), session_id="s1", runtime_dir=Path("/tmp"), start_function=lambda *_args, **_kwargs: Handle())
        runtime.on_file_loaded()
        self.assertFalse(runtime.is_running())
        self.assertEqual(events, ["closed"])


class TestConnectorPackage(unittest.TestCase):
    def test_package_contains_addon_and_shared_harness(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "connector.zip"
            package_connector(target)
            with zipfile.ZipFile(target) as archive:
                names = set(archive.namelist())
            self.assertIn("codex_blender_connector/__init__.py", names)
            self.assertIn("codex_blender_connector/runtime.py", names)
            self.assertIn("codex_blender_connector/harness/session.py", names)
            self.assertIn("codex_blender_connector/harness/frame_pipeline.py", names)
            self.assertIn("codex_blender_connector/harness/frame_worker.py", names)
            self.assertIn("codex_blender_connector/harness/job_worker.py", names)
            self.assertIn("codex_blender_connector/validate_model_in_blender.py", names)
            self.assertNotIn("codex_blender_connector/harness/__pycache__/session.pyc", names)


if __name__ == "__main__":
    unittest.main()
