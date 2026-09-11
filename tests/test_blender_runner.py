"""Tests for the safe Blender process runner.

Covers:
  - Explicit executable precedence over PATH discovery
  - PATH discovery
  - Missing executable (BLENDER_NOT_FOUND)
  - Version output parsing
  - Paths with spaces and Unicode
  - Symlink escape rejection
  - Subprocess spy: shell=False, allowlisted env, captured stdout/stderr, timeout
  - Graceful termination before forced kill (TIMEOUT / CANCELLED)
  - No retry
"""

import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Ensure scripts/ is importable
_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from blender_runner import (
    BlenderCancelledError,
    BlenderError,
    BlenderNotFoundError,
    BlenderRuntime,
    BlenderTimeoutError,
    BlenderUnsupportedVersionError,
    build_argv,
    discover_blender,
    run_blender,
)


def _make_fake_blender(directory: Path, version_output: str = "Blender 4.2.0",
                       script_body: str | None = None) -> Path:
    """Create a minimal executable script that prints *version_output*."""
    blender = directory / "blender"
    body = script_body or textwrap.dedent(f"""\
        #!/usr/bin/env python3
        print("{version_output}")
    """)
    blender.write_text(body)
    blender.chmod(0o755)
    return blender


def _make_sleep_blender(directory: Path, seconds: int = 60) -> Path:
    """Create a fake Blender that sleeps (for timeout/cancellation tests)."""
    blender = directory / "blender"
    blender.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import time
        time.sleep({seconds})
    """))
    blender.chmod(0o755)
    return blender


# ===========================================================================
# A. Executable discovery
# ===========================================================================

class TestDiscoverBlenderExplicitPrecedence(unittest.TestCase):
    """Explicit path wins over PATH discovery."""

    def test_explicit_path_used_over_search_path(self):
        with tempfile.TemporaryDirectory() as td:
            explicit_dir = Path(td) / "explicit"
            explicit_dir.mkdir()
            search_dir = Path(td) / "search"
            search_dir.mkdir()

            explicit_bin = _make_fake_blender(explicit_dir, "Blender 4.2.0")
            _make_fake_blender(search_dir, "Blender 3.6.0")

            runtime = discover_blender(str(explicit_bin), str(search_dir))
            self.assertEqual(runtime.executable, explicit_bin)
            self.assertEqual(runtime.version, "4.2.0")
            self.assertTrue(runtime.background_supported)


class TestDiscoverBlenderFromSearchPath(unittest.TestCase):
    """Blender found in search_path when no explicit path given."""

    def test_found_in_search_path(self):
        with tempfile.TemporaryDirectory() as td:
            search_dir = Path(td) / "bin"
            search_dir.mkdir()
            bin_path = _make_fake_blender(search_dir, "Blender 4.2.0")

            runtime = discover_blender(None, str(search_dir))
            self.assertEqual(runtime.executable, bin_path)
            self.assertEqual(runtime.version, "4.2.0")


# ===========================================================================
# B. Missing executable
# ===========================================================================

class TestDiscoverBlenderMissing(unittest.TestCase):
    """Missing executable raises BlenderNotFoundError, not bare Exception."""

    def test_nonexistent_explicit_path_raises_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            bad_path = os.path.join(td, "no_such_blender")
            with self.assertRaises(BlenderNotFoundError) as ctx:
                discover_blender(bad_path, td)
            self.assertEqual(ctx.exception.category, "BLENDER_NOT_FOUND")

    def test_not_found_in_search_path(self):
        with tempfile.TemporaryDirectory() as td:
            empty_dir = Path(td) / "empty"
            empty_dir.mkdir()
            with self.assertRaises(BlenderNotFoundError) as ctx:
                discover_blender(None, str(empty_dir))
            self.assertEqual(ctx.exception.category, "BLENDER_NOT_FOUND")

    def test_is_blender_error_subclass(self):
        with tempfile.TemporaryDirectory() as td:
            empty_dir = Path(td) / "empty"
            empty_dir.mkdir()
            with self.assertRaises(BlenderError):
                discover_blender(None, str(empty_dir))


# ===========================================================================
# C. Version output parsing
# ===========================================================================

class TestVersionParsing(unittest.TestCase):
    """Parse MAJOR.MINOR.PATCH from Blender --version output."""

    def test_parse_clean_version(self):
        with tempfile.TemporaryDirectory() as td:
            _make_fake_blender(Path(td), "Blender 4.2.0")
            runtime = discover_blender(os.path.join(td, "blender"), td)
            self.assertEqual(runtime.version, "4.2.0")

    def test_parse_version_with_build_hash(self):
        with tempfile.TemporaryDirectory() as td:
            _make_fake_blender(
                Path(td),
                "Blender 4.2.0 (hash abc123 date 2024-07-16)",
            )
            runtime = discover_blender(os.path.join(td, "blender"), td)
            self.assertEqual(runtime.version, "4.2.0")

    def test_parse_version_with_extra_lines(self):
        with tempfile.TemporaryDirectory() as td:
            script_body = textwrap.dedent("""\
                #!/usr/bin/env python3
                print("Blender 4.2.0")
                print("Build: abc123")
                print("Platform: Linux")
            """)
            _make_fake_blender(Path(td), script_body=script_body)
            runtime = discover_blender(os.path.join(td, "blender"), td)
            self.assertEqual(runtime.version, "4.2.0")

    def test_unparseable_version_raises(self):
        with tempfile.TemporaryDirectory() as td:
            _make_fake_blender(Path(td), "no version here")
            with self.assertRaises(BlenderUnsupportedVersionError) as ctx:
                discover_blender(os.path.join(td, "blender"), td)
            self.assertEqual(ctx.exception.category, "UNSUPPORTED_VERSION")


# ===========================================================================
# D. Paths with spaces and Unicode
# ===========================================================================

class TestPathsWithSpacesAndUnicode(unittest.TestCase):
    """Project/request paths containing spaces and Unicode characters."""

    def test_build_argv_with_spaces_in_path(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "my project folder"
            project_dir.mkdir()
            project = project_dir / "scene.blend"
            project.write_text("")
            request = Path(td) / "request.json"
            request.write_text("{}")

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            argv = build_argv(runtime, project, request)
            self.assertIn(str(project), argv)

    def test_build_argv_with_unicode_in_path(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "project_cafe_r\u00e9sum\u00e9"
            project_dir.mkdir()
            project = project_dir / "sc\u00e8ne.blend"
            project.write_text("")
            request = Path(td) / "request.json"
            request.write_text("{}")

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            argv = build_argv(runtime, project, request)
            self.assertIn(str(project), argv)


# ===========================================================================
# E. Symlink escape rejection
# ===========================================================================

class TestSymlinkEscapeRejection(unittest.TestCase):
    """build_argv must reject symlinks that resolve outside project dir."""

    def test_symlink_pointing_outside_project_dir_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "project"
            project_dir.mkdir()
            outside = Path(td) / "outside.blend"
            outside.write_text("")
            evil = project_dir / "evil.blend"
            evil.symlink_to(outside)
            request = Path(td) / "request.json"
            request.write_text("{}")

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            with self.assertRaises(BlenderError):
                build_argv(runtime, evil, request)


# ===========================================================================
# F. build_argv correctness
# ===========================================================================

class TestBuildArgv(unittest.TestCase):
    """Verify argv construction for different versions."""

    def test_basic_argv(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "scene.blend"
            project.write_text("")
            request = Path(td) / "request.json"
            request.write_text("{}")

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            argv = build_argv(runtime, project, request)
            self.assertEqual(argv[0], str(runtime.executable))
            self.assertIn(str(project), argv)
            self.assertIn("--background", argv)

    def test_background_unsupported_older_version(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "scene.blend"
            project.write_text("")
            request = Path(td) / "request.json"
            request.write_text("{}")

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="1.0.0",
                background_supported=False,
            )
            argv = build_argv(runtime, project, request)
            self.assertNotIn("--background", argv)

    def test_engine_flag_varies_by_version(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "scene.blend"
            project.write_text("")
            request = Path(td) / "request.json"
            request.write_text("{}")

            runtime_4x = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            argv_4x = build_argv(runtime_4x, project, request)
            self.assertIn("--engine", argv_4x)
            self.assertIn("CYCLES", argv_4x)
            self.assertNotIn("-E", argv_4x)

            runtime_3x = BlenderRuntime(
                executable=Path(td) / "blender",
                version="3.6.0",
                background_supported=True,
            )
            argv_3x = build_argv(runtime_3x, project, request)
            self.assertIn("-E", argv_3x)
            self.assertIn("CYCLES", argv_3x)
            self.assertNotIn("--engine", argv_3x)


# ===========================================================================
# G. Subprocess spy: shell=False, allowlisted env, captured I/O, timeout
# ===========================================================================

class TestRunBlenderSubprocessSpy(unittest.TestCase):
    """Prove shell=False, allowlisted env, captured stdout/stderr, timeout."""

    def _make_echo_blender(self, directory: Path) -> Path:
        """Fake Blender that echoes argv and env vars."""
        blender = directory / "blender"
        blender.write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import os, sys
            print("ARGS:", " ".join(sys.argv[1:]))
            print("SHELL:", os.environ.get("SHELL", "NOT_SET"))
            print("HOME:", os.environ.get("HOME", "NOT_SET"))
            print("TEST_MARKER:", os.environ.get("TEST_MARKER", "NOT_SET"))
        """))
        blender.chmod(0o755)
        return blender

    def test_shell_false_and_argv_array(self):
        with tempfile.TemporaryDirectory() as td:
            blender = self._make_echo_blender(Path(td))
            result = run_blender([str(blender), "--version"], timeout_seconds=10)
            self.assertEqual(result.returncode, 0)
            self.assertIn("ARGS:", result.stdout)
            self.assertNotIn("sh", result.args[0])

    def test_allowlisted_env_passed(self):
        with tempfile.TemporaryDirectory() as td:
            blender = self._make_echo_blender(Path(td))
            result = run_blender([str(blender), "--version"], timeout_seconds=10)
            self.assertEqual(result.returncode, 0)
            self.assertIn("HOME:", result.stdout)

    def test_non_allowlisted_env_not_leaked(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["TEST_MARKER"] = "should_not_leak"
            try:
                blender = self._make_echo_blender(Path(td))
                result = run_blender(
                    [str(blender), "--version"], timeout_seconds=10
                )
                self.assertIn("TEST_MARKER: NOT_SET", result.stdout)
            finally:
                del os.environ["TEST_MARKER"]

    def test_captured_stdout_and_stderr(self):
        with tempfile.TemporaryDirectory() as td:
            blender = Path(td) / "blender"
            blender.write_text(textwrap.dedent("""\
                #!/usr/bin/env python3
                import sys
                sys.stdout.write("hello_stdout")
                sys.stderr.write("hello_stderr")
            """))
            blender.chmod(0o755)
            result = run_blender([str(blender)], timeout_seconds=10)
            self.assertEqual(result.stdout, "hello_stdout")
            self.assertEqual(result.stderr, "hello_stderr")

    def test_timeout_seconds_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            blender = _make_sleep_blender(Path(td), seconds=60)
            with self.assertRaises(BlenderTimeoutError) as ctx:
                run_blender([str(blender)], timeout_seconds=1)
            self.assertEqual(ctx.exception.category, "TIMEOUT")


# ===========================================================================
# H. Graceful termination before forced kill
# ===========================================================================

class TestGracefulTermination(unittest.TestCase):
    """Cancellation sends SIGTERM before SIGKILL. No retry."""

    def test_cancel_raises_blender_cancelled_error(self):
        with tempfile.TemporaryDirectory() as td:
            blender = Path(td) / "blender"
            blender.write_text(textwrap.dedent("""\
                #!/usr/bin/env python3
                import os, time
                print("PID", os.getpid(), flush=True)
                time.sleep(60)
            """))
            blender.chmod(0o755)

            def _cancel(process):
                process.terminate()

            with self.assertRaises(BlenderCancelledError) as ctx:
                run_blender([str(blender)], timeout_seconds=60, cancel=_cancel)
            self.assertEqual(ctx.exception.category, "CANCELLED")

    def test_timeout_terminates_process(self):
        """After timeout the child process should be dead, not dangling."""
        with tempfile.TemporaryDirectory() as td:
            blender = _make_sleep_blender(Path(td), seconds=60)
            with self.assertRaises(BlenderTimeoutError):
                run_blender([str(blender)], timeout_seconds=1)

            # No dangling process: a new quick script should complete cleanly.
            quick = Path(td) / "quick"
            quick.write_text('#!/usr/bin/env python3\nprint("ok")\n')
            quick.chmod(0o755)
            result = run_blender([str(quick)], timeout_seconds=5)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "ok")


# ===========================================================================
# I. Exception hierarchy
# ===========================================================================

class TestExceptionHierarchy(unittest.TestCase):
    """All runner exceptions carry a stable category string."""

    def test_blender_not_found_category(self):
        with tempfile.TemporaryDirectory() as td:
            empty_dir = Path(td) / "empty"
            empty_dir.mkdir()
            with self.assertRaises(BlenderNotFoundError) as ctx:
                discover_blender(None, str(empty_dir))
            self.assertEqual(ctx.exception.category, "BLENDER_NOT_FOUND")

    def test_unsupported_version_category(self):
        with tempfile.TemporaryDirectory() as td:
            _make_fake_blender(Path(td), "no version here")
            with self.assertRaises(BlenderUnsupportedVersionError) as ctx:
                discover_blender(os.path.join(td, "blender"), td)
            self.assertEqual(ctx.exception.category, "UNSUPPORTED_VERSION")

    def test_timeout_category(self):
        with tempfile.TemporaryDirectory() as td:
            blender = _make_sleep_blender(Path(td), seconds=60)
            with self.assertRaises(BlenderTimeoutError) as ctx:
                run_blender([str(blender)], timeout_seconds=1)
            self.assertEqual(ctx.exception.category, "TIMEOUT")

    def test_cancelled_category(self):
        with tempfile.TemporaryDirectory() as td:
            blender = Path(td) / "blender"
            blender.write_text(textwrap.dedent("""\
                #!/usr/bin/env python3
                import time
                time.sleep(60)
            """))
            blender.chmod(0o755)

            with self.assertRaises(BlenderCancelledError) as ctx:
                run_blender(
                    [str(blender)],
                    timeout_seconds=60,
                    cancel=lambda p: p.terminate(),
                )
            self.assertEqual(ctx.exception.category, "CANCELLED")

    def test_stable_category_strings(self):
        """Category strings match the stable enum exactly."""
        self.assertEqual(BlenderNotFoundError("x").category, "BLENDER_NOT_FOUND")
        self.assertEqual(
            BlenderUnsupportedVersionError("x").category, "UNSUPPORTED_VERSION"
        )
        self.assertEqual(BlenderTimeoutError("x").category, "TIMEOUT")
        self.assertEqual(BlenderCancelledError("x").category, "CANCELLED")


if __name__ == "__main__":
    unittest.main()
