import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.managed_launcher import (
    build_managed_argv,
    launch_managed,
    load_descriptor,
    remove_stale_descriptor,
)


class TestManagedMode(unittest.TestCase):
    def test_policy_reaches_bootstrap_and_actual_runtime_dispatch(self):
        from scripts.harness.execution_policy import ExecutionPolicy
        from scripts.harness.runtime import create_session
        from scripts.managed_bootstrap import _arguments
        from tests.test_design_commands import FakeBpy
        from tests.test_foreground_policy import call
        policy=ExecutionPolicy.review_only()
        argv=build_managed_argv(blender=Path('/app/blender'),project=None,session_id='s',
                                runtime_dir=Path('/tmp/runtime'),execution_policy=policy)
        args=_arguments(argv[argv.index('--')+1:])
        loaded=ExecutionPolicy.from_dict(json.loads(args.execution_policy_json))
        session=create_session(FakeBpy(),'s',execution_policy=loaded)
        self.assertEqual(call(session,'object.create_mesh',{'primitive':'cube','name':'Denied'})['error']['code'],'READ_ONLY_POLICY')

    def test_cli_help_runs_as_a_script(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "harness_cli.py"
        result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, check=False,)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launcher_cli_help_runs_as_a_script(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "launch_harness.py"
        result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, check=False,)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_argv_is_foreground_and_disables_autoexec(self):
        argv = build_managed_argv(
            blender=Path("/Applications/Blender.app/Contents/MacOS/Blender"),
            project=Path("/tmp/project.blend"),
            session_id="s1",
            runtime_dir=Path("/tmp/runtime"),
        )
        self.assertNotIn("--background", argv)
        self.assertIn("--disable-autoexec", argv)
        project=str(Path("/tmp/project.blend"));runtime=str(Path("/tmp/runtime"))
        self.assertIn(project, argv)
        self.assertLess(argv.index("--disable-autoexec"), argv.index(project))
        self.assertEqual(argv[-4:], ["--session-id", "s1", "--runtime-dir", runtime])

    def test_output_root_is_forwarded_to_bootstrap(self):
        argv = build_managed_argv(
            blender=Path("/app/blender"), project=None, session_id="s1",
            runtime_dir=Path("/tmp/runtime"), output_root=Path("/tmp/exports"),
        )
        self.assertEqual(argv[-2:], ["--output-root", str(Path("/tmp/exports"))])

    def test_asset_roots_are_forwarded_to_bootstrap(self):
        argv = build_managed_argv(
            blender=Path("/app/blender"), project=None, session_id="s1",
            runtime_dir=Path("/tmp/runtime"), asset_roots=[Path("/tmp/assets-a"), Path("/tmp/assets-b")],
        )
        self.assertEqual(argv[-4:], ["--asset-root", str(Path("/tmp/assets-a")), "--asset-root", str(Path("/tmp/assets-b"))])

    def test_project_is_optional_for_new_design(self):
        argv = build_managed_argv(
            blender=Path("/Applications/Blender.app/Contents/MacOS/Blender"),
            project=None,
            session_id="s1",
            runtime_dir=Path("/tmp/runtime"),
        )
        self.assertNotIn(".blend", " ".join(argv))

    @patch("scripts.managed_launcher.subprocess.Popen")
    def test_launcher_detaches_blender_from_caller_terminal(self, popen):
        process = popen.return_value
        process.poll.return_value = 1
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(RuntimeError):
            launch_managed(
                blender=Path("/Applications/Blender.app/Contents/MacOS/Blender"),
                project=None,
                session_id="s1",
                runtime_dir=Path(directory),
                timeout=0.1,
            )
        kwargs = popen.call_args.kwargs
        self.assertTrue(kwargs["start_new_session"])
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)

    @unittest.skipIf(os.name == 'nt','POSIX mode bits do not represent Windows ACLs')
    def test_load_descriptor_rejects_world_readable_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "s1.json"
            path.write_text(json.dumps({"token": "secret"}))
            path.chmod(0o644)
            with self.assertRaises(PermissionError):
                load_descriptor(path)

    def test_dead_session_descriptor_and_socket_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            socket_path = root / "session.sock"
            socket_path.write_text("stale")
            descriptor = root / "s1.json"
            descriptor.write_text(json.dumps({"pid": 99999999, "transport": "unix", "address": str(socket_path)}))
            descriptor.chmod(0o600)
            self.assertTrue(remove_stale_descriptor(descriptor))
            self.assertFalse(descriptor.exists())
            self.assertFalse(socket_path.exists())


if __name__ == "__main__":
    unittest.main()
