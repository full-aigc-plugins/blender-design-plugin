import subprocess
import unittest
from pathlib import Path

from scripts.harness.reimport_validator import (
    build_validation_argv,
    parse_validation_output,
    validate_reimport,
)


class TestReimportValidator(unittest.TestCase):
    def test_builds_isolated_blender_argv(self):
        argv = build_validation_argv(Path("/app/blender"), Path("/tmp/model.glb"))
        self.assertEqual(argv[0], str(Path("/app/blender")))
        self.assertIn("--background", argv)
        self.assertIn("--factory-startup", argv)
        self.assertIn("--disable-autoexec", argv)
        self.assertEqual(argv[-2:], ["--", str(Path("/tmp/model.glb"))])

    def test_parses_marked_summary(self):
        output = 'noise\nCODEX_REIMPORT={"objects":2,"meshes":1}\n'
        self.assertEqual(parse_validation_output(output), {"objects": 2, "meshes": 1})

    def test_validate_calls_runner_without_shell(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, 'CODEX_REIMPORT={"objects":1,"meshes":1}\n', '')
        result = validate_reimport(Path("/app/blender"), Path("/tmp/model.obj"), runner=runner)
        self.assertEqual(result["status"], "passed")
        self.assertFalse(calls[0][1]["shell"])


if __name__ == "__main__":
    unittest.main()
