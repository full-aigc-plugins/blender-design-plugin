#!/usr/bin/env python3
"""Start the pinned PartMe Blender MCP runtime bundled with the Codex/ZCode/Kimi plugin.

运行时上游（partme_blender_mcp）逐字不动；本入口以插件侧 PluginMcpAdapter 包装，
在标准工具之外注入 blender_auto_setup / blender_community_* 工具。
传输：默认 stdio；`serve-remote streamable-http|sse` 启动官方 SDK 远程传输。
"""

from __future__ import annotations

import argparse
import os
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
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        from partme_blender_mcp.__main__ import main as runtime_main

        return runtime_main(sys.argv[1:])

    adapter = build_plugin_adapter(McpAdapter, plugin_root=PLUGIN_ROOT)
    if len(sys.argv) > 1 and sys.argv[1] == "serve-remote":
        parser = argparse.ArgumentParser(prog="blender_mcp_server serve-remote")
        parser.add_argument("transport", choices=("streamable-http", "sse"))
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, required=True)
        parser.add_argument("--public-url")
        parser.add_argument("--issuer-url")
        parser.add_argument("--streamable-http-path", default="/mcp")
        parser.add_argument("--sse-path", default="/sse")
        parser.add_argument("--message-path", default="/messages/")
        parser.add_argument("--allowed-host", action="append", default=[])
        parser.add_argument("--allowed-origin", action="append", default=[])
        parser.add_argument("--tls-certfile")
        parser.add_argument("--tls-keyfile")
        parser.add_argument("--status-file")
        args = parser.parse_args(sys.argv[2:])
        from partme_blender_mcp.harness.sdk_server import (
            RemoteServerConfig,
            serve_remote,
        )
        return serve_remote(adapter, RemoteServerConfig(
            transport=args.transport, host=args.host, port=args.port,
            streamable_http_path=args.streamable_http_path, sse_path=args.sse_path,
            message_path=args.message_path, token=os.environ.get("PARTME_BLENDER_REMOTE_TOKEN"),
            public_url=args.public_url, issuer_url=args.issuer_url,
            allowed_hosts=tuple(args.allowed_host), allowed_origins=tuple(args.allowed_origin),
            tls_certfile=args.tls_certfile, tls_keyfile=args.tls_keyfile,
            status_file=args.status_file,
        ))
    return serve_stdio(adapter=adapter)


if __name__ == "__main__":
    raise SystemExit(main())
