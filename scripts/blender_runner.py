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
# Bridge script path (R2)
# ---------------------------------------------------------------------------

_BRIDGE_SCRIPT = Path(__file__).parent / "blender_bridge.py"


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
        BlenderNotFoundError: No executable found or not executable.
        BlenderUnsupportedVersionError: Version output unparseable.
    """
    # --- resolve executable path ---
    if explicit_path is not None:
        exe = Path(explicit_path)
        if not exe.is_file() or not os.access(exe, os.X_OK):  # R1
            raise BlenderNotFoundError(f"Blender not found: {explicit_path}")
    else:
        found = shutil.which("blender", path=search_path)
        if found is None:
            raise BlenderNotFoundError(
                f"Blender not found in search path: {search_path}"
            )
        exe = Path(found)

    # --- probe version ---  (R6: catch TimeoutExpired)
    try:
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            env=_build_env(),
            shell=False,
        )
    except subprocess.TimeoutExpired:
        raise BlenderUnsupportedVersionError(
            f"Blender --version timed out: {exe}"
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

def _check_symlink_escape(path: Path, label: str) -> None:
    """Reject symlinks that resolve outside their parent directory."""
    resolved = path.resolve()
    base = path.parent.resolve()
    if not str(resolved).startswith(str(base) + os.sep):
        raise BlenderError(
            f"{label} path escapes directory via symlink: {path} -> {resolved}",
        )


def build_argv(
    runtime: BlenderRuntime,
    project: Path,
    request: Path,
) -> list[str]:
    """Build the argv list for a Blender invocation.

    Validates that *project* resolves inside its parent directory (symlink
    escape check).  Validates that *request* is not a symlink and is a
    regular file (R3).

    Args:
        runtime: Discovered Blender runtime.
        project: Path to the .blend file.
        request: Path to the request JSON file.

    Returns:
        argv list starting with the Blender executable path.

    Raises:
        BlenderError: If project escapes via symlink or request is a symlink.
    """
    # --- project symlink escape detection ---
    _check_symlink_escape(project, "Project")

    # --- request symlink policy (R3) ---
    if request.is_symlink():
        raise BlenderError(
            f"Request path must not be a symlink: {request}",
        )
    if not request.resolve().is_file():
        raise BlenderError(
            f"Request path must be a regular file: {request}",
        )

    bridge = str(_BRIDGE_SCRIPT)

    argv: list[str] = [str(runtime.executable)]

    # --background gated on runtime support
    if runtime.background_supported:
        argv.append("--background")

    argv.append(str(project))

    # Engine flag varies by major version
    major = int(runtime.version.split(".")[0])
    if major >= 4:
        argv.extend(["--engine", "CYCLES"])
    else:
        argv.extend(["-E", "CYCLES"])

    # Bridge script and request path (R2)
    argv.extend(["--python", bridge, "--", str(request)])

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
    cancel_raised = False

    try:
        while True:
            try:
                cancel(process)  # R7: may raise
            except Exception:
                cancel_raised = True
                raise
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
        # R7: terminate child on every exit path (cancel exception, timeout,
        # or normal).  Guard against already-exited processes.
        if cancel_raised or timed_out:
            try:
                _terminate_or_kill(process)
            except OSError:
                pass
            if timed_out:
                raise BlenderTimeoutError(
                    f"Blender process timed out after {timeout_seconds}s"
                )
            # cancel_raised: the cancel exception is already being propagated

    # Negative return code means killed by signal (e.g. SIGTERM from cancel).
    if process.returncode is not None and process.returncode < 0:
        raise BlenderCancelledError("Blender process was cancelled")

    return CompletedProcess(
        args=argv,
        returncode=process.returncode,
        stdout="".join(out_chunks),
        stderr="".join(err_chunks),
    )
