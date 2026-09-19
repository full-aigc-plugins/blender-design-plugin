#!/usr/bin/env python3
"""Provision and launch the pinned official-SDK PartMe Blender MCP runtime.

The plugin manifests may be started by an arbitrary host Python.  The published
runtime, however, requires Python 3.11-3.13 and the official ``mcp`` package.
This bootstrap verifies the vendored release archive, creates one versioned user
venv on first use, and then replaces itself with the real MCP server process.
All diagnostics go to stderr because stdout belongs exclusively to MCP stdio.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_MIN = (3, 11)
SUPPORTED_MAX = (3, 14)
LOCK_TIMEOUT_SECONDS = 180


class BootstrapError(RuntimeError):
    """The isolated official-SDK runtime could not be prepared."""


def _load_lock(plugin_root: Path) -> tuple[dict, Path, str]:
    lock_path = plugin_root / "runtime.lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        artifact = lock["artifacts"]["runtime"]
        relative = Path(artifact["path"])
        expected = artifact["sha256"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise BootstrapError("runtime.lock.json is missing or invalid") from error
    if relative.is_absolute() or ".." in relative.parts:
        raise BootstrapError("runtime archive path escapes the plugin")
    candidate = plugin_root / relative
    if candidate.is_symlink():
        raise BootstrapError("pinned runtime archive is missing or unsafe")
    archive = candidate.resolve()
    if not archive.is_relative_to(plugin_root) or not archive.is_file():
        raise BootstrapError("pinned runtime archive is missing or unsafe")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != expected:
        raise BootstrapError("pinned runtime archive failed SHA-256 verification")
    return lock, archive, digest


def _cache_root(version: str) -> Path:
    explicit = os.environ.get("PARTME_BLENDER_MCP_CACHE")
    if explicit:
        base = Path(explicit).expanduser()
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches/PartMe/BlenderDesign"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "PartMe/BlenderDesign"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "partme/blender-design"
    return base / "runtime" / version


def _python_version(command: list[str]) -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            [*command, "-c", "import sys;print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        parts = result.stdout.strip().split(".")
        version = (int(parts[0]), int(parts[1]))
        return version if result.returncode == 0 and SUPPORTED_MIN <= version < SUPPORTED_MAX else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _compatible_python() -> list[str]:
    commands: list[list[str]] = []
    explicit = os.environ.get("PARTME_BLENDER_MCP_PYTHON")
    if explicit:
        commands.append([explicit])
    commands.append([sys.executable])
    for name in ("python3.13", "python3.12", "python3.11"):
        resolved = shutil.which(name)
        if resolved:
            commands.append([resolved])
    if os.name == "nt" and shutil.which("py"):
        commands.extend([["py", "-3.13"], ["py", "-3.12"], ["py", "-3.11"]])
    seen = set()
    for command in commands:
        key = tuple(command)
        if key not in seen and _python_version(command) is not None:
            return command
        seen.add(key)
    raise BootstrapError("PartMe Blender MCP requires Python 3.11, 3.12, or 3.13")


def _venv_python(root: Path) -> Path:
    return root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _marker_matches(root: Path, *, version: str, digest: str) -> bool:
    python = _venv_python(root)
    try:
        marker = json.loads((root / "installed.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if marker != {"schemaVersion": "1.0.0", "runtimeVersion": version, "runtimeSha256": digest}:
        return False
    if not python.is_file():
        return False
    probe = subprocess.run(
        [str(python), "-c", (
            "import importlib.metadata as m,partme_blender_mcp;"
            f"assert partme_blender_mcp.__version__=={version!r};"
            "v=tuple(map(int,m.version('mcp').split('.')[:2]));assert (2,2)<=v<(3,0)"
        )],
        capture_output=True, text=True, timeout=30, check=False,
    )
    return probe.returncode == 0


def _acquire_lock(path: Path):
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            return descriptor
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise BootstrapError("timed out waiting for another MCP runtime installation")
            time.sleep(0.25)


def ensure_runtime(plugin_root: Path = PLUGIN_ROOT) -> dict:
    plugin_root = Path(plugin_root).resolve()
    lock, archive, digest = _load_lock(plugin_root)
    version = str(lock["version"])
    root = _cache_root(version)
    root.mkdir(parents=True, exist_ok=True)
    if _marker_matches(root, version=version, digest=digest):
        return {"version": version, "python": str(_venv_python(root)), "cache": str(root), "installed": False}

    lock_path = root / "install.lock"
    descriptor = _acquire_lock(lock_path)
    staging = root / f"venv.staging-{os.getpid()}"
    try:
        if _marker_matches(root, version=version, digest=digest):
            return {"version": version, "python": str(_venv_python(root)), "cache": str(root), "installed": False}
        command = _compatible_python()
        shutil.rmtree(staging, ignore_errors=True)
        print(f"PartMe Blender MCP: installing official SDK runtime {version}...", file=sys.stderr, flush=True)
        subprocess.run([*command, "-m", "venv", str(staging)], check=True, timeout=120)
        staging_python = staging / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [str(staging_python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", str(archive)],
            check=True, timeout=300,
        )
        destination = root / "venv"
        shutil.rmtree(destination, ignore_errors=True)
        staging.replace(destination)
        marker = {"schemaVersion": "1.0.0", "runtimeVersion": version, "runtimeSha256": digest}
        (root / "installed.json").write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
        if not _marker_matches(root, version=version, digest=digest):
            raise BootstrapError("installed MCP runtime failed its import probe")
        return {"version": version, "python": str(_venv_python(root)), "cache": str(root), "installed": True}
    except (OSError, subprocess.SubprocessError) as error:
        raise BootstrapError(f"failed to install official MCP runtime: {error}") from error
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        runtime = ensure_runtime()
        if argv == ["--bootstrap-status"]:
            print(json.dumps(runtime, sort_keys=True))
            return 0
        server = PLUGIN_ROOT / "scripts/blender_mcp_server.py"
        os.execv(runtime["python"], [runtime["python"], str(server), *argv])
    except BootstrapError as error:
        print(f"PartMe Blender MCP bootstrap failed: {error}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
