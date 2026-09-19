"""Streamable HTTP transport for the plugin MCP adapter (POST /mcp + Bearer auth).

与 stdio 同一适配器、同一工具目录。鉴权：Authorization: Bearer <token>，token 来自
--token 参数或 PARTME_BLENDER_HTTP_TOKEN 环境变量；未显式提供时启动期生成并打印一次。
"""

from __future__ import annotations

import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MCP_PROTOCOL_VERSION = "2025-06-18"


def serve_http(adapter, *, host: str, port: int, token: str | None) -> int:
    if not token:
        env_token = __import__("os").environ.get("PARTME_BLENDER_HTTP_TOKEN")
        token = env_token or secrets.token_urlsafe(24)
    if token == "-":
        # explicit opt-out for local trusted use
        token = None

    class HttpMcpHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _deny(self, status: int, body: str):
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _respond(self, status: int, payload: dict):
            body = (json.dumps(payload) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802 - http.server API
            if self.path.rstrip("/") not in ("/mcp", ""):
                return self._deny(404, json.dumps({"error": "not found"}))
            if token is not None:
                header = self.headers.get("Authorization", "")
                if header != f"Bearer {token}":
                    return self._deny(401, json.dumps({"error": "missing or invalid bearer token"}))
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                request = json.loads(raw or b"{}")
                if not isinstance(request, dict):
                    raise ValueError("request must be an object")
            except (ValueError, json.JSONDecodeError):
                return self._deny(400, json.dumps({"error": "invalid JSON body"}))
            method = request.get("method")
            request_id = request.get("id")
            if method == "initialize":
                params = request.get("params") if isinstance(request.get("params"), dict) else {}
                adapter.record_client(params.get("clientInfo"))
                return self._respond(200, {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {
                            "name": "partme-blender-design",
                            "title": "Blender Design MCP (HTTP)",
                            "version": "plugin-http",
                        },
                    },
                })
            if method == "tools/list":
                listing = adapter.list_tools()
                return self._respond(200, {"jsonrpc": "2.0", "id": request_id, "result": listing})
            if method == "tools/call":
                params = request.get("params") if isinstance(request.get("params"), dict) else {}
                outcome = adapter.call_tool(params.get("name"), params.get("arguments"))
                is_error = bool(outcome.get("isError"))
                return self._respond(200, {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": outcome.get("content", []), "isError": is_error},
                })
            if method == "ping":
                return self._respond(200, {"jsonrpc": "2.0", "id": request_id, "result": {}})
            return self._respond(200, {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"method not supported over this transport: {method}"},
            })

        def do_GET(self):  # noqa: N802 - http.server API
            # 无服务器推送场景：SSE 通道不实现，健康探活走简单 JSON。
            if self.path.rstrip("/") in ("/health", "/"):
                body = (json.dumps({"status": "ok", "transport": "http"}) + "\n").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(405)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A002 - http.server API
            print(f"[http-mcp] {format % args}", file=sys.stderr)

    server = ThreadingHTTPServer((host, port), HttpMcpHandler)
    print(
        f"Blender Design MCP (HTTP) listening on http://{host}:{port}/mcp "
        + (f"(Authorization: Bearer {token})" if token else "(auth disabled)"),
        file=sys.stderr,
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
