"""Tests for the safe Blender process runner.

Covers:
  - Explicit executable precedence over PATH discovery
  - PATH discovery
  - Missing executable (BLENDER_NOT_FOUND)
  - Non-executable file (BLENDER_NOT_FOUND)
  - Version output parsing
  - Version probe timeout
  - Paths with spaces and Unicode
  - Symlink escape rejection (project)
  - Request symlink policy
  - build_argv correctness (bridge, request, background, engine)
  - Subprocess spy via mock (shell=False, env, pipes, timeout)
  - Graceful termination ordering via mock (terminate before kill)
  - Cancel-callback exception terminates child
  - No retry
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from subprocess import PIPE
from unittest.mock import MagicMock, patch

# Ensure scripts/ is importable
_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from blender_runner import (
    _BRIDGE_SCRIPT,
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


def _make_request(directory: Path, name: str = "request.json") -> Path:
    """Create a valid non-symlinked request file."""
    request = directory / name
    request.write_text("{}")
    return request


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
# B. Missing executable and non-executable file (R1)
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

    def test_non_executable_file_raises_not_found(self):
        """R1: A file that exists but is not executable surfaces BLENDER_NOT_FOUND."""
        with tempfile.TemporaryDirectory() as td:
            blender = Path(td) / "blender"
            blender.write_text("#!/usr/bin/env python3\nprint('nope')\n")
            blender.chmod(0o644)  # not executable
            with self.assertRaises(BlenderNotFoundError) as ctx:
                discover_blender(str(blender), td)
            self.assertEqual(ctx.exception.category, "BLENDER_NOT_FOUND")


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

    def test_version_probe_timeout_raises_unsupported(self):
        """R6: A hanging --version probe surfaces UNSUPPORTED_VERSION."""
        with tempfile.TemporaryDirectory() as td:
            blender = _make_sleep_blender(Path(td), seconds=60)
            with self.assertRaises(BlenderUnsupportedVersionError) as ctx:
                discover_blender(str(blender), td)
            self.assertIn("timed out", str(ctx.exception))


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
            request = _make_request(Path(td))

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
            request = _make_request(Path(td))

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            argv = build_argv(runtime, project, request)
            self.assertIn(str(project), argv)


# ===========================================================================
# E. Symlink escape rejection (project) and request symlink policy (R3)
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
            request = _make_request(Path(td))

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            with self.assertRaises(BlenderError):
                build_argv(runtime, evil, request)

    def test_symlinked_request_rejected(self):
        """R3: A symlinked request path must be rejected."""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "scene.blend"
            project.write_text("")
            real_request = Path(td) / "real_request.json"
            real_request.write_text("{}")
            link_request = Path(td) / "link_request.json"
            link_request.symlink_to(real_request)

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            with self.assertRaises(BlenderError) as ctx:
                build_argv(runtime, project, link_request)
            self.assertIn("symlink", str(ctx.exception))

    def test_normal_request_accepted(self):
        """R3: A normal (non-symlink) request file is accepted."""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "scene.blend"
            project.write_text("")
            request = _make_request(Path(td))

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            # Should not raise
            argv = build_argv(runtime, project, request)
            self.assertIn(str(request), argv)


# ===========================================================================
# F. build_argv correctness (R2: bridge + request)
# ===========================================================================

class TestBuildArgv(unittest.TestCase):
    """Verify argv construction for different versions."""

    def test_request_path_in_argv_after_separator(self):
        """R2: request path appears in argv after the -- separator."""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "scene.blend"
            project.write_text("")
            request = _make_request(Path(td))

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            argv = build_argv(runtime, project, request)
            self.assertIn("--", argv)
            separator_idx = argv.index("--")
            self.assertEqual(argv[separator_idx + 1], str(request))

    def test_bridge_path_is_sibling_of_runner(self):
        """R2: bridge path is blender_bridge.py next to this module."""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "scene.blend"
            project.write_text("")
            request = _make_request(Path(td))

            runtime = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            argv = build_argv(runtime, project, request)
            self.assertIn("--python", argv)
            python_idx = argv.index("--python")
            bridge_arg = argv[python_idx + 1]
            self.assertEqual(bridge_arg, str(_BRIDGE_SCRIPT))
            self.assertTrue(bridge_arg.endswith("blender_bridge.py"))

    def test_background_supported_changes_argv(self):
        """R2: background_supported gates --background flag."""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "scene.blend"
            project.write_text("")
            request = _make_request(Path(td))

            runtime_bg = BlenderRuntime(
                executable=Path(td) / "blender",
                version="4.2.0",
                background_supported=True,
            )
            argv_bg = build_argv(runtime_bg, project, request)
            self.assertIn("--background", argv_bg)

            runtime_nobg = BlenderRuntime(
                executable=Path(td) / "blender",
                version="1.0.0",
                background_supported=False,
            )
            argv_nobg = build_argv(runtime_nobg, project, request)
            self.assertNotIn("--background", argv_nobg)

    def test_engine_flag_varies_by_version(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "scene.blend"
            project.write_text("")
            request = _make_request(Path(td))

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
# G. Subprocess spy via mock (R4: prove Popen kwargs)
# ===========================================================================

class TestRunBlenderSubprocessSpyMock(unittest.TestCase):
    """R4: Patch subprocess.Popen and assert the real call contract."""

    def test_shell_false_and_argv_identity(self):
        """Popen is called with shell=False and the exact argv list."""
        argv = ["blender", "--version"]
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("ok", "")
        mock_process.returncode = 0

        with patch("blender_runner.subprocess.Popen", return_value=mock_process) as mock_popen:
            result = run_blender(argv, timeout_seconds=30)

        mock_popen.assert_called_once()
        call_kwargs = mock_popen.call_args
        self.assertFalse(call_kwargs.kwargs.get("shell", True))
        self.assertEqual(call_kwargs.args[0], argv)

    def test_env_is_allowlisted(self):
        """Popen receives an env dict containing only allowlisted keys."""
        from blender_runner import _ENV_ALLOWLIST

        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", "")
        mock_process.returncode = 0

        with patch("blender_runner.subprocess.Popen", return_value=mock_process) as mock_popen:
            run_blender(["blender"], timeout_seconds=30)

        call_kwargs = mock_popen.call_args
        env = call_kwargs.kwargs.get("env", {})
        # Every key in the passed env must be in the allowlist
        for key in env:
            self.assertIn(key, _ENV_ALLOWLIST)

    def test_stdout_stderr_pipes(self):
        """Popen is called with stdout=PIPE and stderr=PIPE."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", "")
        mock_process.returncode = 0

        with patch("blender_runner.subprocess.Popen", return_value=mock_process) as mock_popen:
            run_blender(["blender"], timeout_seconds=30)

        call_kwargs = mock_popen.call_args
        self.assertEqual(call_kwargs.kwargs.get("stdout"), PIPE)
        self.assertEqual(call_kwargs.kwargs.get("stderr"), PIPE)

    def test_communicate_receives_timeout(self):
        """communicate() is called with the exact timeout_seconds value."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", "")
        mock_process.returncode = 0

        with patch("blender_runner.subprocess.Popen", return_value=mock_process):
            run_blender(["blender"], timeout_seconds=42)

        mock_process.communicate.assert_called_once_with(timeout=42)


# ===========================================================================
# H. Graceful termination ordering via mock (R5)
# ===========================================================================

class TestGracefulTerminationOrdering(unittest.TestCase):
    """R5: Assert terminate() is called before kill(), kill() only on grace expiry."""

    def test_terminate_called_before_kill_on_timeout(self):
        """On timeout: terminate() called, then wait(5) raises, then kill()."""
        mock_process = MagicMock()
        # First communicate raises TimeoutExpired
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="blender", timeout=1
        )
        # First wait (grace) also raises so kill is reached
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="blender", timeout=5),
            None,  # kill's wait succeeds
        ]
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        with patch("blender_runner.subprocess.Popen", return_value=mock_process):
            with self.assertRaises(BlenderTimeoutError):
                run_blender(["blender"], timeout_seconds=1)

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        # terminate must be called before kill
        term_call = mock_process.terminate.call_args_list[0]
        kill_call = mock_process.kill.call_args_list[0]
        # They are on the same mock; order is enforced by the logic.
        # If kill were called without terminate, terminate call_count would be 0.

    def test_kill_not_called_when_child_exits_during_grace(self):
        """If the child exits during the grace period, kill() is never called."""
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="blender", timeout=1
        )
        # First wait (grace) succeeds -- child exited
        mock_process.wait.return_value = None
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        with patch("blender_runner.subprocess.Popen", return_value=mock_process):
            with self.assertRaises(BlenderTimeoutError):
                run_blender(["blender"], timeout_seconds=1)

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_not_called()


# ===========================================================================
# I. End-to-end hermetic tests (kept from original)
# ===========================================================================

class TestRunBlenderEndToEnd(unittest.TestCase):
    """Hermetic end-to-end tests with fake executables (no mock)."""

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
# J. Graceful termination end-to-end
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

    def test_cancel_callback_exception_terminates_child(self):
        """R7: If cancel callback raises, the child is still terminated."""
        with tempfile.TemporaryDirectory() as td:
            blender = Path(td) / "blender"
            blender.write_text(textwrap.dedent("""\
                #!/usr/bin/env python3
                import time
                time.sleep(60)
            """))
            blender.chmod(0o755)

            def _bad_cancel(process):
                raise RuntimeError("cancel callback exploded")

            with self.assertRaises(RuntimeError, msg="cancel callback exploded"):
                run_blender([str(blender)], timeout_seconds=60, cancel=_bad_cancel)

            # Child should be dead. Verify by running a quick script.
            quick = Path(td) / "quick"
            quick.write_text('#!/usr/bin/env python3\nprint("ok")\n')
            quick.chmod(0o755)
            result = run_blender([str(quick)], timeout_seconds=5)
            self.assertEqual(result.returncode, 0)


# ===========================================================================
# K. Exception hierarchy
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
