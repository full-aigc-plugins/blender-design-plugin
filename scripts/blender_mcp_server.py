#!/usr/bin/env python3
"""Start the pinned PartMe Blender MCP runtime bundled with the Codex/ZCode/Kimi plugin.

运行时上游（partme_blender_mcp）逐字不动；本入口以插件侧 PluginMcpAdapter 包装，
在标准工具之外注入 blender_auto_setup / blender_community_* 工具。
传输：默认 stdio；`--http <port>` 切换 Streamable HTTP（Bearer 鉴权，token 来自
--token 或 PARTME_BLENDER_HTTP_TOKEN，缺省自动生成并在启动时打印）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.partme_runtime import activate_runtime

activate_runtime(PLUGIN_ROOT)

from partme_blender_mcp.harness.mcp_adapter import McpAdapter, serve_stdio

from scripts.plugin_mcp_adapter import build_plugin_adapter


def main() -> int:
    parser = argparse.ArgumentParser(prog="blender_mcp_server", description="Blender Design MCP server (stdio or HTTP)")
    parser.add_argument("--http", metavar="PORT", type=int, default=None, help="serve Streamable HTTP on PORT instead of stdio")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default 127.0.0.1)")
    parser.add_argument("--token", default=None, help="HTTP bearer token; defaults to PARTME_BLENDER_HTTP_TOKEN or an auto-generated one; '-' disables auth")
    args, passthrough = parser.parse_known_args()

    if passthrough and (passthrough[0] == "doctor"):
        from partme_blender_mcp.__main__ import main as runtime_main

        return runtime_main(passthrough)

    adapter = build_plugin_adapter(McpAdapter, plugin_root=PLUGIN_ROOT)

    if args.http is not None:
        from scripts.http_transport import serve_http

        return serve_http(adapter, host=args.host, port=args.http, token=args.token)
    return serve_stdio(adapter=adapter)


if __name__ == "__main__":
    raise SystemExit(main())
