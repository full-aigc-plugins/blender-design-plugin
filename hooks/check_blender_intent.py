#!/usr/bin/env python3
"""UserPromptSubmit hook: point blender-shaped requests at the plugin commands.

Advisory only — always exits 0 and only prints when the prompt looks
Blender-related. Skips slash commands (they already route explicitly).
"""
from __future__ import annotations

import json
import re
import sys

INTENT_RE = re.compile(
    r"blender|白模|预演|previs|建模|三维|3\s*d|渲染|rig|骨骼|材质|拓扑|雕刻|分镜运镜",
    re.IGNORECASE,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    prompt = ""
    if isinstance(payload, dict):
        prompt = str(payload.get("prompt") or "")

    if prompt.strip().startswith("/"):
        return 0 # explicit command, no advice needed

    if INTENT_RE.search(prompt):
        print(
            "提示：该请求疑似 Blender 相关。可用 /blender 总入口或细分命令 "
            "(/blender-design /blender-previs /blender-inspect /blender-preview "
            "/blender-export /blender-render /blender-recover /blender-dreamina)；"
            "MCP 工具经 partme_blender 提供。"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
