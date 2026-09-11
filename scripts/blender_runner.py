"""Safe Blender process runner: discovery, argv construction, subprocess execution.

Find a user-installed Blender, parse its version, build an argv array,
and execute it safely with an allowlisted environment.  Never uses shell=True,
never installs Blender, never modifies PATH.
"""

import os
import re
import select
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import Callable

_POLL_INTERVAL = 0.1  # seconds between cancel/callback checks

def _monotonic() -> float:
    return time.monotonic()

def _terminate_or_kill(process: subprocess.Popen) -> None:
    """Graceful termination (SIGTERM) then forced kill (SIGKILL)."""
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BlenderRuntime:
    executable: Path
    version: str
    background_supported: bool


# ---------------------------------------------------------------------------
# Exception hierarchy with stable category strings
# ---------------------------------------------------------------------------

class BlenderError(Exception):
    """Base exception for all Blender runner failures."""
    category: str = "UNKNOWN"

    def __init__(self, message: str, category: str | None = None):
        super().__init__(message)
        if category is not None:
            self.category = category


class BlenderNotFoundError(BlenderError):
    category = "BLENDER_NOT_FOUND"

    def __init__(self, message: str):
        super().__init__(message, category="BLENDER_NOT_FOUND")


class BlenderUnsupportedVersionError(BlenderError):
    category = "UNSUPPORTED_VERSION"

    def __init__(self, message: str):
        super().__init__(message, category="UNSUPPORTED_VERSION")


class BlenderTimeoutError(BlenderError):
    category = "TIMEOUT"

    def __init__(self, message: str):
        super().__init__(message, category="TIMEOUT")


class BlenderCancelledError(BlenderError):
    category = "CANCELLED"

    def __init__(self, message: str):
        super().__init__(message, category="CANCELLED")


class BlenderProjectNotAuthorizedError(BlenderError):
    category = "PROJECT_NOT_AUTHORIZED"

    def __init__(self, message: str):
        super().__init__(message, category="PROJECT_NOT_AUTHORIZED")


class BlenderCameraNotFoundError(BlenderError):
    category = "CAMERA_NOT_FOUND"

    def __init__(self, message: str):
        super().__init__(message, category="CAMERA_NOT_FOUND")


class BlenderInvalidFrameRangeError(BlenderError):
    category = "INVALID_FRAME_RANGE"

    def __init__(self, message: str):
        super().__init__(message, category="INVALID_FRAME_RANGE")


class BlenderRenderFailedError(BlenderError):
    category = "RENDER_FAILED"

    def __init__(self, message: str):
        super().__init__(message, category="RENDER_FAILED")


class BlenderRestoreUnconfirmedError(BlenderError):
    category = "RESTORE_UNCONFIRMED"

    def __init__(self, message: str):
        super().__init__(message, category="RESTORE_UNCONFIRMED")


class BlenderMediaInvalidError(BlenderError):
    category = "MEDIA_INVALID"

    def __init__(self, message: str):
        super().__init__(message, category="MEDIA_INVALID")


# ---------------------------------------------------------------------------
# Version parsing
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _parse_version(output: str) -> str:
    """Extract the first MAJOR.MINOR.PATCH from Blender --version output.

    Raises BlenderUnsupportedVersionError if no parseable version is found.
    """
    match = _VERSION_RE.search(output)
    if match is None:
        raise BlenderUnsupportedVersionError(
            f"Could not parse version from Blender output: {output!r}"
        )
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))


def _background_supported(version: str) -> bool:
    """Background mode is supported on Blender >= 2.80."""
    return _version_tuple(version) >= (2, 80, 0)


# ---------------------------------------------------------------------------
# Environment allowlist (ruling 4)
# ---------------------------------------------------------------------------

_ENV_ALLOWLIST = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}
if sys.platform == "win32":
    _ENV_ALLOWLIST.update({"SYSTEMROOT", "PATHEXT"})


def _build_env() -> dict[str, str]:
    """Return a minimal environment dict with only OS-essential variables."""
    env: dict[str, str] = {}
    for key in _ENV_ALLOWLIST:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    return env


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_blender(explicit_path: str | None, search_path: str) -> BlenderRuntime:
    """Locate a Blender executable and probe its version.

    Args:
        explicit_path: Full path to a Blender binary, or None to search.
        search_path:  Directory to search for ``blender`` when no explicit path.

    Returns:
        BlenderRuntime with parsed version and background support flag.

    Raises:
        BlenderNotFoundError: No executable found.
        BlenderUnsupportedVersionError: Version output unparseable.
    """
    # --- resolve executable path ---
    if explicit_path is not None:
        exe = Path(explicit_path)
        if not exe.is_file():
            raise BlenderNotFoundError(f"Blender not found: {explicit_path}")
    else:
        found = shutil.which("blender", path=search_path)
        if found is None:
            raise BlenderNotFoundError(
                f"Blender not found in search path: {search_path}"
            )
        exe = Path(found)

    # --- probe version ---
    result = subprocess.run(
        [str(exe), "--version"],
        capture_output=True,
        text=True,
        timeout=15,
        env=_build_env(),
        shell=False,
    )
    output = result.stdout.strip()
    if not output:
        output = result.stderr.strip()

    version = _parse_version(output)
    bg = _background_supported(version)

    return BlenderRuntime(executable=exe, version=version, background_supported=bg)


# ---------------------------------------------------------------------------
# argv construction
# ---------------------------------------------------------------------------

def build_argv(
    runtime: BlenderRuntime,
    project: Path,
    request: Path,
) -> list[str]:
    """Build the argv list for a Blender invocation.

    Validates that *project* resolves inside *project*'s parent directory
    (symlink escape check).

    Args:
        runtime: Discovered Blender runtime.
        project: Path to the .blend file.
        request: Path to the request JSON file.

    Returns:
        argv list starting with the Blender executable path.

    Raises:
        BlenderError: If the project path escapes via symlink.
    """
    # --- symlink escape detection ---
    project_resolved = project.resolve()
    base = project.parent.resolve()
    if not str(project_resolved).startswith(str(base) + os.sep):
        raise BlenderError(
            f"Project path escapes project directory via symlink: {project} -> {project_resolved}",
        )

    argv: list[str] = [str(runtime.executable), str(project)]

    if runtime.background_supported:
        argv.append("--background")

    # Engine flag varies by major version
    major = int(runtime.version.split(".")[0])
    if major >= 4:
        argv.extend(["--engine", "CYCLES"])
    else:
        argv.extend(["-E", "CYCLES"])

    return argv


# ---------------------------------------------------------------------------
# Safe subprocess execution
# ---------------------------------------------------------------------------

def run_blender(
    argv: list[str],
    timeout_seconds: int,
    cancel: Callable | None = None,
) -> CompletedProcess[str]:
    """Execute Blender as a subprocess with strict safety constraints.

    Args:
        argv: Command as an argv list (never interpolated into a shell string).
        timeout_seconds: Maximum seconds before the child is killed.
        cancel: Optional callback receiving the Popen object.  If it calls
                ``process.terminate()``, the runner raises BlenderCancelledError.

    Returns:
        CompletedProcess[str] on success.

    Raises:
        BlenderTimeoutError:  Child exceeded *timeout_seconds*.
        BlenderCancelledError: *cancel* callback terminated the child.
    """
    env = _build_env()

    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        shell=False,
    )

    # When a cancel callback is provided we must poll so the callback can
    # terminate the child while it is still running.  Without a callback
    # we can use the simpler communicate() path.
    if cancel is None:
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate_or_kill(process)
            process.stdout.close()  # type: ignore[union-attr]
            process.stderr.close()  # type: ignore[union-attr]
            raise BlenderTimeoutError(
                f"Blender process timed out after {timeout_seconds}s"
            )
        return CompletedProcess(
            args=argv,
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    # --- polling path (cancel callback present) ---
    out_chunks: list[str] = []
    err_chunks: list[str] = []
    deadline = _monotonic() + timeout_seconds
    timed_out = False

    try:
        while True:
            cancel(process)
            rc = process.poll()
            if rc is not None:
                break

            # Read available data without blocking indefinitely.
            ready = select.select(
                [process.stdout, process.stderr], [], [], _POLL_INTERVAL
            )[0]
            if process.stdout in ready:
                chunk = process.stdout.read(65536)
                if chunk:
                    out_chunks.append(chunk)
            if process.stderr in ready:
                chunk = process.stderr.read(65536)
                if chunk:
                    err_chunks.append(chunk)

            if _monotonic() > deadline:
                timed_out = True
                break

        # Drain any remaining data in the pipe buffers.
        if not timed_out:
            while True:
                chunk = process.stdout.read(65536)  # type: ignore[union-attr]
                if not chunk:
                    break
                out_chunks.append(chunk)
            while True:
                chunk = process.stderr.read(65536)  # type: ignore[union-attr]
                if not chunk:
                    break
                err_chunks.append(chunk)
    finally:
        process.stdout.close()  # type: ignore[union-attr]
        process.stderr.close()  # type: ignore[union-attr]

    if timed_out:
        _terminate_or_kill(process)
        raise BlenderTimeoutError(
            f"Blender process timed out after {timeout_seconds}s"
        )

    # Negative return code means killed by signal (e.g. SIGTERM from cancel).
    if process.returncode is not None and process.returncode < 0:
        raise BlenderCancelledError("Blender process was cancelled")

    return CompletedProcess(
        args=argv,
        returncode=process.returncode,
        stdout="".join(out_chunks),
        stderr="".join(err_chunks),
    )
