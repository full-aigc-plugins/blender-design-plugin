"""Tests for the community bridge, HTTP transport, and dual-install auto setup."""

import json
import socket
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from scripts import auto_setup, community_bridge
from scripts.community_bridge import CommunityBridgeError, community_status

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _fake_community_server(responses: dict | None = None):
    """One-shot TCP server speaking the community addon JSON protocol."""
    responses = responses or {}

    class Server(threading.Thread):
        daemon = True

        def __init__(self):
            super().__init__()
            self.sock = socket.socket()
            self.sock.bind(("127.0.0.1", 0))
            self.sock.listen(1)
            self.port = self.sock.getsockname()[1]
            self.seen = []

        def run(self):
            conn, _ = self.sock.accept()
            data = bytearray()
            while not data.endswith(b"\n"):
                block = conn.recv(65536)
                if not block:
                    break
                data.extend(block)
            self.seen.append(json.loads(data.decode()))
            command = self.seen[-1]["type"]
            reply = responses.get(command, {"status": "success", "result": {"pong": True}})
            conn.sendall((json.dumps(reply) + "\n").encode())
            conn.close()

    server = Server()
    server.start()
    return server


class CommunityBridgeTests(unittest.TestCase):
    def test_allowlist_covers_all_providers(self):
        for provider in ("polyhaven", "sketchfab", "hyper3d", "hunyuan3d"):
            self.assertTrue(any(g == provider for g in community_bridge.COMMUNITY_COMMANDS.values()))
        self.assertNotIn("polypizza", set(community_bridge.COMMUNITY_COMMANDS.values()))
        # execute_code 与遥测命令刻意不在白名单：社区的原生代码执行会绕过
        # PartMe Harness 的守卫（事务/审批/恢复），宿主侧必须走我们的受控命令面。
        self.assertNotIn("execute_code", community_bridge.COMMUNITY_COMMANDS)
        self.assertNotIn("set_telemetry_consent", community_bridge.COMMUNITY_COMMANDS)

    def test_unknown_command_rejected(self):
        with self.assertRaises(CommunityBridgeError) as ctx:
            community_bridge.call_community("rm_rf_everything")
        self.assertEqual(ctx.exception.code, "UNKNOWN_COMMAND")

    def test_direct_community_import_is_blocked_with_partme_migration(self):
        with self.assertRaises(CommunityBridgeError) as ctx:
            community_bridge.call_community("import_generated_asset", {"url": "https://example.test/a.glb"})
        self.assertEqual(ctx.exception.code, "COMMUNITY_COMMAND_REQUIRES_PARTME_FLOW")

    def test_risk_levels_separate_generation_from_polling(self):
        self.assertEqual(community_bridge.command_risk("create_rodin_job"), "paid_generation")
        self.assertEqual(community_bridge.command_risk("poll_rodin_job_status"), "read")
        self.assertEqual(community_bridge.command_risk("export_scene"), "external_export")

    def test_roundtrip_success(self):
        server = _fake_community_server({
            "ping": {"status": "success", "result": {"pong": True}},
            "get_scene_info": {"status": "success", "result": {"objects": 3}},
        })
        try:
            result = community_bridge.call_community("get_scene_info", {}, port=server.port)
            self.assertEqual(result, {"objects": 3})
            self.assertEqual(server.seen[0]["type"], "get_scene_info")
        finally:
            server.sock.close()

    def test_error_envelope_raises(self):
        server = _fake_community_server({
            "ping": {"status": "error", "message": "no key"},
        })
        try:
            with self.assertRaises(CommunityBridgeError) as ctx:
                community_bridge.call_community("ping", {}, port=server.port)
            self.assertEqual(ctx.exception.code, "COMMUNITY_COMMAND_FAILED")
        finally:
            server.sock.close()

    def test_unreachable_is_structured(self):
        status = {}
        with mock.patch.object(community_bridge, "COMMUNITY_PORT", 59999):
            try:
                status = community_status()
            except CommunityBridgeError:
                self.fail("status must degrade, not raise")
        self.assertFalse(status.get("connected"))
        self.assertEqual(status.get("error"), "COMMUNITY_ADDON_UNREACHABLE")


class CommunityToolsRegistrationTests(unittest.TestCase):
    def test_tool_definitions_reference_real_commands(self):
        from scripts.plugin_mcp_adapter import COMMUNITY_CALL_TOOL, COMMUNITY_STATUS_TOOL

        self.assertEqual(COMMUNITY_STATUS_TOOL["name"], "blender_community_status")
        enum = COMMUNITY_CALL_TOOL["inputSchema"]["properties"]["command"]["enum"]
        self.assertEqual(set(enum), set(community_bridge.COMMUNITY_COMMANDS))
        self.assertEqual(COMMUNITY_CALL_TOOL["name"], "blender_community_call")

    def test_real_plugin_adapter_paginates_the_combined_catalog_once(self):
        from scripts.partme_runtime import activate_runtime

        activate_runtime(PLUGIN_ROOT)
        from partme_blender_mcp.harness.mcp_adapter import McpAdapter
        from scripts.plugin_mcp_adapter import build_plugin_adapter

        adapter = build_plugin_adapter(McpAdapter, plugin_root=PLUGIN_ROOT, bridge=mock.Mock())
        names = []
        cursor = None
        while True:
            page = adapter.list_tools(cursor=cursor, limit=7)
            self.assertLessEqual(len(page["tools"]), 7)
            names.extend(tool["name"] for tool in page["tools"])
            cursor = page.get("nextCursor")
            if cursor is None:
                break
        self.assertEqual(len(names), len(set(names)))
        for name in ("blender_auto_setup", "blender_community_status", "blender_community_call"):
            self.assertEqual(names.count(name), 1)

    def test_provider_contribution_excludes_duplicate_polypizza(self):
        catalog = json.loads((PLUGIN_ROOT / "config/providers.json").read_text(encoding="utf-8"))
        ids = [provider["providerId"] for provider in catalog["providers"]]
        self.assertEqual(ids, ["polyhaven", "sketchfab", "hyper3d", "hunyuan3d"])
        self.assertNotIn("polypizza", ids)


class DualInstallTests(unittest.TestCase):
    def test_happy_path_installs_both_addons(self):
        with tempfile.TemporaryDirectory() as tmp:
            script_root = Path(tmp) / "4.5" / "scripts"
            from tests.test_auto_setup import _fake_blender, _make_addon_zip

            blender_bin = _fake_blender(script_root)
            launched = mock.Mock(pid=9999)
            with mock.patch.object(auto_setup, "discover_blender", return_value=blender_bin), \
                 mock.patch.object(auto_setup, "blender_running", return_value=False), \
                 mock.patch.object(auto_setup, "launch_connected", return_value=launched), \
                 mock.patch.dict(__import__("os").environ, {"PARTME_BLENDER_OUTPUT_ROOT": str(Path(tmp) / "out")}):
                result = auto_setup.run_auto_setup(PLUGIN_ROOT)
            steps = {s["step"]: s for s in result["steps"]}
            self.assertTrue(steps["install"]["ok"])
            self.assertTrue(steps["install-community"]["ok"], steps.get("install-community"))
            addons = script_root / "addons"
            self.assertTrue((addons / "partme_blender_mcp").is_dir())
            self.assertTrue((addons / "partme_blender_mcp" / "providers.json").is_file())
            self.assertTrue((addons / "blender_mcp_community").is_dir())
            self.assertTrue((addons / "blender_mcp_community" / "__init__.py").is_file())


class HttpTransportTests(unittest.TestCase):
    def test_http_serves_tools_list_with_bearer(self):
        import time

        from scripts import http_transport

        class FakeAdapter:
            def record_client(self, info):
                pass

            def list_tools(self):
                return {"tools": [
                    {"name": "blender_auto_setup"},
                    {"name": "blender_community_status"},
                    {"name": "blender_community_call"},
                ], "nextCursor": None}

            def call_tool(self, name, arguments):
                return {"content": [{"type": "text", "text": "{}"}], "isError": False}

        adapter = FakeAdapter()
        bearer = "test" + "-token-123"
        captured = {}

        class CaptureServer(http_transport.ThreadingHTTPServer):
            def __init__(self, addr, handler):
                super().__init__(addr, handler)
                captured["server"] = self

        real_ths = http_transport.ThreadingHTTPServer
        http_transport.ThreadingHTTPServer = CaptureServer
        try:
            threading.Thread(
                target=lambda: http_transport.serve_http(adapter, host="127.0.0.1", port=0, token=bearer),
                daemon=True,
            ).start()
            for _ in range(100):
                if "server" in captured:
                    break
                time.sleep(0.05)
            server = captured.get("server")
            self.assertIsNotNone(server)
            port = server.server_address[1]

            def post(body: dict, headers: dict):
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/mcp",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json", **headers},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    return response.status, json.loads(response.read().decode())

            status, payload = post(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                {"Authorization": "Bearer " + bearer},
            )
            self.assertEqual(status, 200)
            names = [t["name"] for t in payload["result"]["tools"]]
            self.assertIn("blender_auto_setup", names)
            self.assertIn("blender_community_call", names)

            with self.assertRaises(urllib.error.HTTPError) as denied:
                post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, {"Authorization": "Bearer wrong"})
            self.assertEqual(denied.exception.code, 401)
        finally:
            http_transport.ThreadingHTTPServer = real_ths
            server = captured.get("server")
            if server:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
