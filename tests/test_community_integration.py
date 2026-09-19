"""Tests for the community bridge, HTTP transport, and dual-install auto setup."""

import json
import socket
import tempfile
import threading
import unittest
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
        from scripts.plugin_mcp_adapter import (
            COMMUNITY_CALL_TOOL,
            COMMUNITY_STATUS_TOOL,
            PROVIDER_STAGE_TOOL,
            PROVIDER_TASKS_TOOL,
        )

        self.assertEqual(COMMUNITY_STATUS_TOOL["name"], "blender_community_status")
        enum = COMMUNITY_CALL_TOOL["inputSchema"]["properties"]["command"]["enum"]
        self.assertEqual(set(enum), set(community_bridge.COMMUNITY_COMMANDS))
        self.assertEqual(COMMUNITY_CALL_TOOL["name"], "blender_community_call")
        self.assertIn("_estimatedCost", COMMUNITY_CALL_TOOL["inputSchema"]["properties"])
        self.assertEqual(PROVIDER_TASKS_TOOL["name"], "blender_provider_tasks")
        self.assertEqual(PROVIDER_STAGE_TOOL["name"], "blender_provider_stage_asset")
        self.assertNotIn("resolve_sketchfab_download", enum)

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
        for name in ("blender_auto_setup", "blender_community_status", "blender_community_call",
                     "blender_provider_tasks", "blender_provider_stage_asset"):
            self.assertEqual(names.count(name), 1)

    def test_provider_contribution_excludes_duplicate_polypizza(self):
        catalog = json.loads((PLUGIN_ROOT / "config/providers.json").read_text(encoding="utf-8"))
        ids = [provider["providerId"] for provider in catalog["providers"]]
        self.assertEqual(ids, ["polyhaven", "sketchfab", "hyper3d", "hunyuan3d"])
        self.assertNotIn("polypizza", ids)
        orders = {provider["providerId"]: provider["metadata"]["uiOrder"] for provider in catalog["providers"]}
        self.assertEqual(orders, {"polyhaven": 20, "sketchfab": 30, "hyper3d": 10, "hunyuan3d": 20})
        for provider in catalog["providers"]:
            metadata = provider.get("metadata", {})
            self.assertRegex(metadata.get("statusCommand", ""), r"^get_[a-z0-9_]+_status$")
            self.assertRegex(metadata.get("enableProperty", ""), r"^blendermcp_use_[a-z0-9_]+$")
            self.assertEqual(metadata.get("preferencesModule"), "blender_mcp_community")
            self.assertIs(type(provider.get("enabled")), bool)
            self.assertIs(type(provider.get("configurable")), bool)

    def test_disabled_community_provider_is_rejected_before_real_command(self):
        from scripts.partme_runtime import activate_runtime

        activate_runtime(PLUGIN_ROOT)
        from partme_blender_mcp.harness.mcp_adapter import McpAdapter

        from scripts.plugin_mcp_adapter import build_plugin_adapter

        adapter = build_plugin_adapter(McpAdapter, plugin_root=PLUGIN_ROOT, bridge=mock.Mock())

        def community_call(command, _params):
            if command == "get_sketchfab_status":
                return {"enabled": False, "message": "Sketchfab is disabled"}
            self.fail(f"disabled provider command reached community add-on: {command}")

        with mock.patch("scripts.community_bridge.call_community", side_effect=community_call):
            result = adapter.call_tool("blender_community_call", {
                "command": "search_sketchfab_models",
                "params": {"query": "chair"},
            })

        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"]["code"], "PROVIDER_DISABLED")

    def test_provider_stage_keeps_signed_url_out_of_mcp_result(self):
        from scripts.partme_runtime import activate_runtime

        activate_runtime(PLUGIN_ROOT)
        from partme_blender_mcp.harness.mcp_adapter import McpAdapter

        from scripts.plugin_mcp_adapter import build_plugin_adapter

        bridge = mock.Mock()
        bridge.call.return_value = {
            "status": "succeeded",
            "sceneRevision": 1,
            "result": {
                "path": "/approved/generated/sketchfab/chair/model.gltf",
                "sourceHost": "download.sketchfab.com",
            },
        }
        adapter = build_plugin_adapter(McpAdapter, plugin_root=PLUGIN_ROOT, bridge=bridge)
        signed_url = "https://download.sketchfab.com/model.zip?signature=secret"

        def community_call(command, _params, **kwargs):
            if command == "get_sketchfab_status":
                return {"enabled": True, "message": "Sketchfab is enabled"}
            self.assertEqual(command, "resolve_sketchfab_download")
            self.assertTrue(kwargs.get("allow_internal"))
            return {"providerId": "sketchfab", "url": signed_url, "filename": "chair.zip"}

        with mock.patch("scripts.community_bridge.call_community", side_effect=community_call):
            result = adapter.call_tool("blender_provider_stage_asset", {
                "providerId": "sketchfab",
                "params": {"uid": "chair"},
                "_requestId": "stage-1",
                "_transactionId": "tx-1",
                "_expectedSceneRevision": 0,
                "_authorization": "one-time-claim",
            })

        self.assertFalse(result["isError"])
        self.assertNotIn(signed_url, json.dumps(result))
        stage_call = bridge.call.call_args
        self.assertEqual(stage_call.args[0], "asset.fetch_generated")
        self.assertEqual(stage_call.args[1]["url"], signed_url)
        self.assertEqual(stage_call.kwargs["authorization"], "one-time-claim")

    def test_generation_create_reports_provider_neutral_task_to_blender(self):
        from scripts.partme_runtime import activate_runtime

        activate_runtime(PLUGIN_ROOT)
        from partme_blender_mcp.harness.mcp_adapter import McpAdapter

        from scripts.plugin_mcp_adapter import build_plugin_adapter

        bridge = mock.Mock()
        bridge.call.return_value = {"status": "succeeded", "result": {}}
        adapter = build_plugin_adapter(McpAdapter, plugin_root=PLUGIN_ROOT, bridge=bridge)

        def community_call(command, _params):
            if command == "get_hyper3d_status":
                return {"enabled": True, "message": "Hyper3D is enabled"}
            return {"subscription_key": "sub-42"}

        with mock.patch("scripts.community_bridge.call_community", side_effect=community_call):
            result = adapter.call_tool("blender_community_call", {
                "command": "create_rodin_job",
                "params": {"text_prompt": "chair"},
                "_requestId": "request-1",
                "_transactionId": "transaction-1",
                "_expectedSceneRevision": 0,
                "_estimatedCost": "0.75",
            })

        self.assertFalse(result["isError"])
        updates = [call for call in bridge.call.call_args_list if call.args[0] == "provider.task_control"]
        self.assertEqual(len(updates), 1)
        gate = next(call for call in bridge.call.call_args_list if call.args[0] == "provider.external_action")
        self.assertEqual(gate.args[1]["estimatedCost"], "0.75")
        self.assertEqual(updates[0].args[1]["providerId"], "hyper3d")
        self.assertEqual(updates[0].args[1]["taskId"], "sub-42")
        self.assertEqual(updates[0].args[1]["state"], "generating")

    def test_local_cancel_stops_future_poll_without_calling_provider(self):
        from scripts.partme_runtime import activate_runtime

        activate_runtime(PLUGIN_ROOT)
        from partme_blender_mcp.harness.mcp_adapter import McpAdapter

        from scripts.plugin_mcp_adapter import build_plugin_adapter

        bridge = mock.Mock()

        def bridge_call(command, arguments, **_kwargs):
            if command == "provider.task_control" and arguments["operation"] == "status":
                return {"status": "succeeded", "result": {
                    "providerId": "hunyuan3d", "taskId": "job-42", "state": "cancelled",
                    "cancelRequested": True, "remoteMayContinue": True,
                    "message": "已停止等待，远端任务可能仍在运行",
                }}
            return {"status": "succeeded", "result": {}}

        bridge.call.side_effect = bridge_call
        adapter = build_plugin_adapter(McpAdapter, plugin_root=PLUGIN_ROOT, bridge=bridge)
        with mock.patch("scripts.community_bridge.call_community") as community_call:
            result = adapter.call_tool("blender_community_call", {
                "command": "poll_hunyuan_job_status",
                "params": {"job_id": "job-42"},
            })

        community_call.assert_not_called()
        self.assertEqual(result["structuredContent"]["status"], "cancelled")
        self.assertTrue(result["structuredContent"]["remoteMayContinue"])

    def test_poll_recreates_missing_runtime_task_before_updating_it(self):
        from scripts.partme_runtime import activate_runtime

        activate_runtime(PLUGIN_ROOT)
        from partme_blender_mcp.harness.mcp_adapter import McpAdapter

        from scripts.plugin_mcp_adapter import build_plugin_adapter

        bridge = mock.Mock()

        def bridge_call(command, arguments, **_kwargs):
            if command != "provider.task_control":
                return {"status": "succeeded", "result": {}}
            if arguments["operation"] in {"status", "update"}:
                return {"status": "failed", "error": {"code": "PROVIDER_TASK_NOT_FOUND"}}
            return {"status": "succeeded", "result": dict(arguments)}

        bridge.call.side_effect = bridge_call
        adapter = build_plugin_adapter(McpAdapter, plugin_root=PLUGIN_ROOT, bridge=bridge)

        def community_call(command, _params):
            if command == "get_hunyuan3d_status":
                return {"enabled": True, "message": "Hunyuan3D is enabled"}
            return {"job_id": "job-recovered", "status": "PROCESSING", "progress": 35}

        with mock.patch("scripts.community_bridge.call_community", side_effect=community_call):
            result = adapter.call_tool("blender_community_call", {
                "command": "poll_hunyuan_job_status",
                "params": {"job_id": "job-recovered"},
            })

        self.assertFalse(result["isError"])
        operations = [
            call.args[1]["operation"] for call in bridge.call.call_args_list
            if call.args[0] == "provider.task_control"
        ]
        self.assertEqual(operations, ["status", "update", "start"])
        self.assertEqual(result["structuredContent"]["_partmeTask"]["operation"], "start")


class DualInstallTests(unittest.TestCase):
    def test_happy_path_installs_both_addons(self):
        with tempfile.TemporaryDirectory() as tmp:
            script_root = Path(tmp) / "4.5" / "scripts"
            blender_bin = Path(tmp) / "blender"
            launched = mock.Mock(pid=9999)
            with mock.patch.object(auto_setup, "discover_blender", return_value=blender_bin), \
                 mock.patch.object(auto_setup, "blender_running", return_value=False), \
                 mock.patch.object(auto_setup, "resolve_scripts_root", return_value=script_root / "addons"), \
                 mock.patch.object(auto_setup, "enable_addon_persistently", return_value=True), \
                 mock.patch.object(auto_setup, "configure_partme_runtime", return_value=True), \
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


if __name__ == "__main__":
    unittest.main()
