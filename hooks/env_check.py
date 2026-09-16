#!/usr/bin/env python3
"""SessionStart hook: report Blender readiness for this plugin.

Advisory only — always exits 0. Stdout is a short Chinese summary intended
to be injected into session context by the host (Claude-format hooks).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

DISK_WARN_BYTES = 20 * 1024 * 1024 * 1024  # 20GB

BLENDER_CANDIDATES = [
    "/Applications/Blender.app/Contents/MacOS/Blender",
    "/Applications/Blender/Blender.app/Contents/MacOS/Blender",
]


def find_blender() -> str:
    for candidate in BLENDER_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    found = shutil.which("blender") or shutil.which("Blender")
    return found or ""


def stale_sockets() -> list[str]:
    base = Path(os.environ.get("TMPDIR", "/tmp")) / "codex-blender"
    if not base.is_dir():
        return []
    hits = []
    for pattern in ("*.sock", "*.socket"):
        hits.extend(str(p) for p in base.glob(pattern))
    return sorted(hits)


def main() -> int:
    lines: list[str] = []

    blender = find_blender()
    if blender:
        lines.append(f"Blender: {blender}")
    else:
        lines.append("Blender: 未找到（/Applications/Blender.app 或 PATH 中均无）；涉及建模/渲染的请求前需先安装")

    lines.append(f"python3: {sys.version.split()[0]} at {Path(sys.executable)}")

    try:
        usage = shutil.disk_usage(Path.cwd() or Path.home())
        free_gb = usage.free / 1024**3
        if free_gb < DISK_WARN_BYTES / 1024**3:
            lines.append(f"磁盘: 仅剩 {free_gb:.1f}GB —— 渲染与导出可能失败，建议先清理")
        else:
            lines.append(f"磁盘: {free_gb:.1f}GB 可用")
    except OSError:
        pass

    sockets = stale_sockets()
    if sockets:
        lines.append(f"残留 socket: {len(sockets)} 个于 codex-blender 临时目录，可能是上次会话未收尾")

    # Consume stdin if present so the writer never sees EPIPE; payload unused.
    try:
        sys.stdin.read()
    except Exception:
        pass

    print("Blender 插件环境：" + "；".join(lines))
    return 0


if __name__ == "__main__":
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    sys.exit(main())
