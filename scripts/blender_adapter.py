"""Preview-only adapter entry point for codex-dreamina-3d."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from blender_runner import BlenderError, build_argv, discover_blender, run_blender
from media_probe import MediaProbeError, probe_media


ROOT = Path(__file__).resolve().parents[1]
PREVIEW_BRIDGE = ROOT / "scripts" / "preview_only_bridge.py"
INSPECTION_BRIDGE = ROOT / "scripts" / "blender_bridge.py"
DEFAULT_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
PRODUCER_VERSION = "0.1.0"


class AdapterError(RuntimeError):
    """Adapter failure carrying a stable category."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category



def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--status", action="store_true")
    return parser


def _read_request(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AdapterError("INVALID_REQUEST", f"request is not a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterError("INVALID_REQUEST", str(exc)) from exc
    if not isinstance(payload, dict):
        raise AdapterError("INVALID_REQUEST", "request root must be an object")
    scene = Path(str(payload.get("scene", "")))
    if not scene.is_absolute() or scene.is_symlink() or not scene.is_file():
        raise AdapterError("PROJECT_NOT_AUTHORIZED", f"scene is not an authorized file: {scene}")
    return payload


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _run_blender_request(
    request: dict[str, Any],
    *,
    request_path: Path,
    output_path: Path | None,
    mode: str,
) -> dict[str, Any]:
    scene = Path(str(request["scene"])).resolve()
    output_path = output_path.resolve() if output_path is not None else None
    explicit = request.get("blender_executable")
    if explicit is not None:
        explicit_path = Path(str(explicit))
        if not explicit_path.is_absolute():
            raise AdapterError("INVALID_REQUEST", "blender_executable must be absolute")
        executable = str(explicit_path)
    elif DEFAULT_BLENDER.is_file():
        executable = str(DEFAULT_BLENDER)
    else:
        executable = None

    try:
        runtime = discover_blender(executable, os.environ.get("PATH", ""))
    except BlenderError as exc:
        raise AdapterError(exc.category, str(exc)) from exc

    inner_request = dict(request)
    inner_request["projectPath"] = str(scene)
    if output_path is not None:
        inner_request["output_path"] = str(output_path)

    fd, raw_inner = tempfile.mkstemp(
        prefix=f".{request_path.stem}.", suffix=".blender.json", dir=str(request_path.parent)
    )
    os.close(fd)
    inner_path = Path(raw_inner)
    try:
        _atomic_write_json(inner_path, inner_request)
        bridge = INSPECTION_BRIDGE if mode == "inspect" else PREVIEW_BRIDGE
        argv = build_argv(runtime, scene, inner_path, bridge_path=bridge)
        try:
            completed = run_blender(argv, timeout_seconds=int(request.get("timeout_seconds", 120)))
        except BlenderError as exc:
            raise AdapterError(exc.category, str(exc)) from exc
    finally:
        if inner_path.exists():
            inner_path.unlink()

    if completed.returncode != 0:
        raise AdapterError("BLENDER_FAILED", completed.stderr.strip() or f"Blender exited {completed.returncode}")
    child = _extract_json(completed.stdout)
    if mode == "inspect":
        return {"status": "inspect_ok", "scene": str(scene), "scene_receipt": child}

    if output_path is None:
        raise AdapterError("INVALID_REQUEST", "output path is required")
    rendered = Path(str(child.get("rendered_path", ""))).resolve()
    if not rendered.is_file():
        raise AdapterError("RENDER_FAILED", f"Blender produced no preview: {rendered}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if rendered != output_path:
        try:
            os.replace(rendered, output_path)
        except OSError:
            shutil.move(str(rendered), str(output_path))
    try:
        media = probe_media(output_path)
    except MediaProbeError as exc:
        raise AdapterError("MEDIA_INVALID", str(exc)) from exc

    frame_range = child.get("frame_range") or request.get("frame_range")
    return {
        "schema_version": "1.0.0",
        "producer_plugin": "codex-blender",
        "producer_version": PRODUCER_VERSION,
        "artifact_id": str(request.get("artifact_id") or ""),
        "path": str(output_path),
        **media,
        "camera": {"name": str(child.get("camera") or request.get("camera_name") or "")},
        "frame_range": frame_range,
        "preview_mode": "camera_render",
        "restoration": child.get("restoration") or {"status": "unknown"},
    }


def _extract_json(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise AdapterError("BLENDER_FAILED", "Blender produced no JSON result")


def _emit(payload: dict[str, Any], *, stream: Any | None = None) -> None:
    print(json.dumps(payload, sort_keys=True), file=stream or sys.stdout)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    request_path = Path(args.request)
    receipt_path = Path(args.receipt)

    if args.status:
        if receipt_path.is_file():
            try:
                _emit(json.loads(receipt_path.read_text(encoding="utf-8")))
                return 0
            except (OSError, json.JSONDecodeError):
                pass
        _emit({"status": "unknown"})
        return 0

    if not args.inspect and not args.output:
        _emit({"category": "INVALID_REQUEST", "message": "--output is required for export"}, stream=sys.stderr)
        return 2

    try:
        request = _read_request(request_path)
        raw_output = Path(args.output) if args.output else None
        if raw_output is not None and raw_output.is_symlink():
            raise AdapterError("OUTPUT_NOT_AUTHORIZED", "output path must not be a symlink")
        output_path = raw_output.resolve() if raw_output is not None else None
        result = _run_blender_request(
            request,
            request_path=request_path,
            output_path=output_path,
            mode="inspect" if args.inspect else "export",
        )
        if not args.inspect and result.get("restoration", {}).get("status") != "confirmed":
            raise AdapterError("RESTORE_UNCONFIRMED", "preview restoration was not confirmed")
        _atomic_write_json(receipt_path, result)
        return 0
    except AdapterError as exc:
        _emit({"category": exc.category, "message": str(exc)}, stream=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
