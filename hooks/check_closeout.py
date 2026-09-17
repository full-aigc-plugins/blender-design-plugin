#!/usr/bin/env python3
"""Stop hook: remind about unfinished Blender work before the turn ends.

Advisory only — always exits 0, prints only when live blender-design state
(active sockets / checkpoints) is found under $TMPDIR/blender-design.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

STATE_PATTERNS = ("*.sock", "*.socket", "*checkpoint*")


def live_state() -> list[str]:
    base = Path(os.environ.get("TMPDIR", "/tmp")) / "blender-design"
    if not base.is_dir():
        return []
    hits: list[str] = []
    for pattern in STATE_PATTERNS:
        hits.extend(str(p) for p in base.glob(pattern))
    return sorted(set(hits))


def main() -> int:
    hits = live_state()
    if hits:
        print(
            f"提醒：blender-design 仍有 {len(hits)} 项活跃状态（socket/checkpoint），"
            "确认后台作业已收尾、事务已提交或回滚后再结束本轮。"
        )
    try:
        sys.stdin.read()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
