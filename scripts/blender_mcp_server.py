#!/usr/bin/env python3
"""Start the pinned PartMe Blender MCP runtime bundled with the Codex/ZCode/Kimi plugin.

运行时上游（partme_blender_mcp）逐字不动；本入口以插件侧 PluginMcpAdapter 包装，
在标准工具之外注入 blender_auto_setup（首次使用自动安装并连接）。
"""

from __future__ import annotations

import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.partme_runtime import activate_runtime

activate_runtime(PLUGIN_ROOT)

from partme_blender_mcp.harness.mcp_adapter import McpAdapter, serve_stdio

from scripts.plugin_mcp_adapter import build_plugin_adapter


if __name__ == "__main__":
    argv = sys.argv[1:]
    passthrough = bool(argv) and (argv[0] == "doctor" or argv[0].startswith("-"))
    if passthrough:
        from partme_blender_mcp.__main__ import main as runtime_main

        raise SystemExit(runtime_main(argv))
    adapter = build_plugin_adapter(McpAdapter, plugin_root=PLUGIN_ROOT)
    raise SystemExit(serve_stdio(adapter=adapter))
