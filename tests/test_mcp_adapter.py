import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RecordingBridge:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or {
            "protocolVersion": "codex-blender/v1",
            "requestId": "returned",
            "status": "succeeded",
            "sceneRevision": 4,
            "changedObjects": [],
            "warnings": [],
            "result": {"ok": True},
        }

    def status(self):
        return {"connected": True, "sessionId": "connector-test", "sceneRevision": 3}

    def call(self, command, arguments, **envelope):
        self.calls.append((command, arguments, envelope))
        return dict(self.response)


class TestNativeMcpCatalog(unittest.TestCase):
    def test_command_names_use_portable_single_underscore_snake_case(self):
        from scripts.harness.mcp_adapter import command_tool_name

        self.assertEqual(command_tool_name("animation.pose_keyframe"),
                         "blender_animation_pose_keyframe")

    def test_every_registered_harness_command_has_one_mcp_tool(self):
        from scripts.harness.mcp_adapter import build_tool_catalog, command_tool_name
        from scripts.harness.runtime import build_registry
        from types import SimpleNamespace

        bpy = SimpleNamespace(app=SimpleNamespace(version=(5, 2, 1), background=False,
                                                   version_string="5.2.1"))
        registry = build_registry(bpy)
        tools = build_tool_catalog(registry=registry, plugin_root=ROOT)
        by_name = {tool["name"]: tool for tool in tools}

        for capability in registry.capabilities():
            tool_name = command_tool_name(capability["command"])
            self.assertIn(tool_name, by_name, capability["command"])
            description = registry.describe_capability({"id": capability["command"]})
            schema = by_name[tool_name]["inputSchema"]
            for required in description["input"].get("required", []):
                self.assertIn(required, schema.get("required", []), capability["command"])
            self.assertFalse(schema["additionalProperties"])
            if capability["risk"] != "read":
                self.assertIn("_transactionId", schema.get("required", []), capability["command"])

        command_tools = [tool for tool in tools if tool.get("_meta", {}).get("codexBlenderCommand")]
        self.assertEqual(len(command_tools), len(registry.capabilities()))
        self.assertEqual(len({tool["name"] for tool in tools}), len(tools))
        self.assertTrue(all("__" not in tool["name"] for tool in command_tools))

    def test_catalog_rejects_command_name_collisions(self):
        from scripts.harness.mcp_adapter import McpAdapterError, build_tool_catalog
        from scripts.harness.registry import CommandRegistry
        from scripts.harness.commands.validation import closed_arguments

        registry = CommandRegistry()
        registry.register("a.b_c", lambda _args: {}, validate=closed_arguments())
        registry.register("a_b.c", lambda _args: {}, validate=closed_arguments())
        with self.assertRaises(McpAdapterError) as caught:
            build_tool_catalog(registry=registry, plugin_root=ROOT)
        self.assertEqual(caught.exception.code, "MCP_TOOL_NAME_COLLISION")

    def test_onboarding_tools_are_available_without_blender(self):
        from scripts.harness.mcp_adapter import McpAdapter

        adapter = McpAdapter(bridge=None, plugin_root=ROOT)
        result = adapter.call_tool("blender_getting_started", {})
        payload = result["structuredContent"]
        self.assertEqual(payload["downloadUrl"], "https://www.blender.org/download/")
        self.assertIn("还没有 Blender？下载安装包", payload["copy"]["zhCN"])
        self.assertIn("Start MCP Server", payload["copy"]["zhCN"])
        self.assertEqual(len(payload["screenshots"]), 2)
        for screenshot in payload["screenshots"]:
            self.assertTrue(Path(screenshot["path"]).is_file(), screenshot)

    def test_default_catalog_is_the_connector_superset(self):
        from scripts.harness.mcp_adapter import McpAdapter

        names = {tool["name"] for tool in McpAdapter(bridge=None, plugin_root=ROOT).tools}
        self.assertIn("blender_official_uploader_inspect", names)
        self.assertIn("blender_official_uploader_render_and_link", names)
        self.assertIn("blender_export_file", names)

    def test_control_tool_annotations_do_not_claim_read_only(self):
        from scripts.harness.mcp_adapter import McpAdapter

        tools = {tool["name"]: tool for tool in McpAdapter(bridge=None, plugin_root=ROOT).tools}
        for name in ("blender_transaction_begin", "blender_transaction_commit",
                     "blender_transaction_rollback", "blender_authorize"):
            self.assertFalse(tools[name]["annotations"]["readOnlyHint"], name)
        self.assertTrue(tools["blender_transaction_rollback"]["annotations"]["destructiveHint"])


class TestNativeMcpForwarding(unittest.TestCase):
    def test_registered_tool_forwards_closed_arguments_and_envelope(self):
        from scripts.harness.mcp_adapter import McpAdapter

        bridge = RecordingBridge()
        adapter = McpAdapter(bridge=bridge, plugin_root=ROOT)
        result = adapter.call_tool("blender_scene_inspect", {
            "_requestId": "inspect-1", "_transactionId": "audit"
        })
        self.assertFalse(result["isError"])
        self.assertEqual(bridge.calls, [(
            "scene.inspect", {},
            {"request_id": "inspect-1", "transaction_id": "audit",
             "expected_scene_revision": None, "authorization": None},
        )])

    def test_harness_failure_is_returned_as_a_tool_error(self):
        from scripts.harness.mcp_adapter import McpAdapter

        bridge = RecordingBridge(response={
            "status": "failed", "sceneRevision": 2, "changedObjects": [], "warnings": [],
            "error": {"code": "AUTHORIZATION_REQUIRED", "message": "confirmation required",
                      "retryable": False},
        })
        result = McpAdapter(bridge=bridge, plugin_root=ROOT).call_tool(
            "blender_object_delete", {"name": "Cube", "_transactionId": "milestone-1"}
        )
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"]["code"], "AUTHORIZATION_REQUIRED")
        self.assertEqual(bridge.calls[0][2]["expected_scene_revision"], 3)

    def test_unknown_fields_are_rejected_before_harness_dispatch(self):
        from scripts.harness.mcp_adapter import McpAdapter

        bridge = RecordingBridge()
        result = McpAdapter(bridge=bridge, plugin_root=ROOT).call_tool(
            "blender_scene_inspect", {"shell": "unsafe"}
        )
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(bridge.calls, [])


class TestDescriptorBridge(unittest.TestCase):
    def test_descriptor_token_is_used_but_never_reported(self):
        from scripts.harness.mcp_adapter import DescriptorBridge

        with tempfile.TemporaryDirectory() as directory:
            descriptor_path = Path(directory) / "connector.json"
            descriptor_path.write_text(json.dumps({
                "protocolVersion": "codex-blender/v1", "sessionId": "connector-1",
                "transport": "tcp", "address": ["127.0.0.1", 12345],
                "token": "private-token", "pid": 42,
            }))
            descriptor_path.chmod(0o600)
            sent = []

            bridge = DescriptorBridge(
                descriptor_path=descriptor_path,
                process_alive=lambda _pid: True,
                sender=lambda endpoint, token, payload: sent.append((endpoint, token, payload)) or {
                    "status": "succeeded", "sceneRevision": 0, "result": {"ok": True}},
            )
            status = bridge.status()
            bridge.call("scene.inspect", {}, request_id="r1", transaction_id="audit")
            self.assertNotIn("token", status)
            self.assertNotIn("private-token", json.dumps(status))
            self.assertEqual(status["sceneRevision"], 0)
            self.assertEqual(sent[0][1], "private-token")
            self.assertEqual(sent[0][2]["command"], "session.status")
            self.assertEqual(sent[1][2]["command"], "scene.inspect")

    def test_symlink_descriptor_is_rejected(self):
        from scripts.harness.mcp_adapter import DescriptorBridge, McpAdapterError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "real.json"
            target.write_text("{}")
            link = root / "link.json"
            link.symlink_to(target)
            with self.assertRaises(McpAdapterError) as caught:
                DescriptorBridge(descriptor_path=link).status()
            self.assertEqual(caught.exception.code, "UNSAFE_DESCRIPTOR")


class TestStdioLifecycle(unittest.TestCase):
    def test_initialize_list_and_call_use_json_rpc(self):
        from scripts.harness.mcp_adapter import McpAdapter, serve_stdio

        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "blender_getting_started", "arguments": {}}},
        ]
        output = io.StringIO()
        code = serve_stdio(
            io.StringIO("".join(json.dumps(request) + "\n" for request in requests)),
            output,
            McpAdapter(bridge=None, plugin_root=ROOT),
        )
        messages = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(code, 0)
        self.assertEqual([message["id"] for message in messages], [1, 2, 3])
        self.assertEqual(messages[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertTrue(messages[0]["result"]["capabilities"]["tools"])
        self.assertIn("tools", messages[1]["result"])
        self.assertIn("structuredContent", messages[2]["result"])

    def test_tools_list_is_paginated_without_duplicates(self):
        from scripts.harness.mcp_adapter import McpAdapter

        adapter = McpAdapter(bridge=None, plugin_root=ROOT)
        names = []
        cursor = None
        while True:
            page = adapter.list_tools(cursor=cursor)
            self.assertLessEqual(len(page["tools"]), 50)
            names.extend(tool["name"] for tool in page["tools"])
            cursor = page.get("nextCursor")
            if cursor is None:
                break
        self.assertEqual(len(names), len(adapter.tools))
        self.assertEqual(len(names), len(set(names)))

    def test_invalid_tools_cursor_is_a_json_rpc_parameter_error(self):
        from scripts.harness.mcp_adapter import McpAdapter, serve_stdio

        request = {"jsonrpc": "2.0", "id": 8, "method": "tools/list",
                   "params": {"cursor": "not-a-cursor"}}
        output = io.StringIO()
        serve_stdio(io.StringIO(json.dumps(request) + "\n"), output,
                    McpAdapter(bridge=None, plugin_root=ROOT))
        message = json.loads(output.getvalue())
        self.assertEqual(message["error"]["code"], -32602)


if __name__ == "__main__":
    unittest.main()
