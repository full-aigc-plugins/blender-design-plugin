"""Plugin-side MCP adapter: upstream runtime tools plus blender_auto_setup.

上游 vendored runtime 保持逐字不动；本模块以子类包装注入插件自有工具，
让首次使用的用户无需任何手动步骤即可建立 Blender MCP 连接。
"""

from __future__ import annotations

import time
from pathlib import Path

from scripts.auto_setup import run_auto_setup, wait_for_connection
from scripts.community_bridge import COMMUNITY_COMMANDS, PROVIDERS, CommunityBridgeError, community_status


def _mcp_error(code: str, message: str):
    from partme_blender_mcp.harness.mcp_adapter import McpAdapterError

    return McpAdapterError(code, message)

AUTO_SETUP_TOOL = {
    "name": "blender_auto_setup",
    "title": "Automatically install and connect Blender",
    "description": (
        "First-run automatic setup: discover the local Blender installation, install the "
        "PartMe Blender MCP Add-on into it, enable it persistently, and launch Blender with "
        "the connector auto-started so the guarded session becomes reachable. Call this "
        "whenever blender_connection_status reports no connection and the user wants to "
        "connect. Falls back to the bundled offline add-on package when GitHub is unreachable."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "outputRoot": {
                "type": "string",
                "description": "Approved output directory for AI exports. Defaults to ~/partme/blender/design-outputs.",
            },
            "launchBlender": {
                "type": "boolean",
                "description": "Launch Blender with the connector auto-started after enabling the add-on. Default true.",
            },
            "waitSeconds": {
                "type": "integer",
                "minimum": 0,
                "maximum": 120,
                "description": "Seconds to wait for the connection to come up before returning. Default 20.",
            },
        },
        "additionalProperties": False,
    },
    "outputSchema": {"type": "object"},
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
}


_COMMUNITY_COMMAND_LIST = ", ".join(sorted(COMMUNITY_COMMANDS))
_PROVIDER_LIST = ", ".join(p for p in PROVIDERS if p != "base")

COMMUNITY_STATUS_TOOL = {
    "name": "blender_community_status",
    "title": "Community asset providers status",
    "description": (
        "Check the vendored community Add-on (blender_mcp_community, MIT) inside Blender and list "
        f"its asset providers ({_PROVIDER_LIST}) with per-provider command surfaces. The community "
        "Add-on listens on 127.0.0.1:9876 and is installed/enabled automatically by blender_auto_setup."
    ),
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    "outputSchema": {"type": "object"},
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
}

COMMUNITY_CALL_TOOL = {
    "name": "blender_community_call",
    "title": "Call a community asset provider command",
    "description": (
        "Run one allowlisted command on the vendored community Add-on (127.0.0.1:9876). Providers: "
        f"{_PROVIDER_LIST}. Allowed commands: {_COMMUNITY_COMMAND_LIST}. Provider API keys "
        "(Sketchfab / Poly Pizza / Hyper3D / Hunyuan3D) are user-supplied in the community Add-on's "
        "Blender preferences; PolyHaven needs no key. Typical flows: search_polyhaven_assets then "
        "download_polyhaven_asset; create_rodin_job then poll_rodin_job_status then "
        "import_generated_asset."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "enum": sorted(COMMUNITY_COMMANDS), "description": "Community command name"},
            "params": {"type": "object", "description": "Command parameters as defined by the community Add-on"},
        },
        "required": ["command"],
        "additionalProperties": False,
    },
    "outputSchema": {"type": "object"},
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
}


def build_plugin_adapter(base_adapter_cls, *, plugin_root: Path | None = None, **kwargs):
    """Return a subclass instance of the vendored McpAdapter with blender_auto_setup added."""

    plugin_root = Path(plugin_root or Path(__file__).resolve().parents[1]).resolve()

    class PluginMcpAdapter(base_adapter_cls):
        _plugin_root = plugin_root

        def list_tools(self, *, cursor: str | None = None, limit: int = 50) -> dict:
            result = super().list_tools(cursor=cursor, limit=limit)
            tools = result.get("tools", [])
            for extra in (AUTO_SETUP_TOOL, COMMUNITY_STATUS_TOOL, COMMUNITY_CALL_TOOL):
                if not any(tool.get("name") == extra["name"] for tool in tools):
                    tools.append(dict(extra))
            return {**result, "tools": tools}

        def call_tool(self, name: str, arguments: dict | None):
            if name == AUTO_SETUP_TOOL["name"]:
                arguments = dict(arguments or {})
                unknown = sorted(set(arguments) - set(AUTO_SETUP_TOOL["inputSchema"]["properties"]))
                if unknown:
                    from partme_blender_mcp.harness.mcp_adapter import McpAdapterError

                    return self._error(McpAdapterError("INVALID_ARGUMENT", f"unknown fields: {unknown}"))
                output_root = arguments.pop("outputRoot", None)
                launch = arguments.pop("launchBlender", True)
                wait_seconds = arguments.pop("waitSeconds", 20)
                result = run_auto_setup(
                    self._plugin_root,
                    output_root=Path(output_root) if output_root else None,
                    launch_blender=bool(launch),
                )
                if result.get("stage") == "launch":
                    try:
                        wait_for_connection(
                            lambda: self._active_bridge().status(),
                            seconds=int(wait_seconds),
                        )
                        result["connected"] = True
                        try:
                            result["connectionStatus"] = self._active_bridge().status()
                        except Exception:  # noqa: BLE001 - status is best-effort
                            pass
                    except Exception:  # noqa: BLE001 - keep partial result with manual hint
                        pass
                return self._result(result)
            if name == COMMUNITY_STATUS_TOOL["name"]:
                if arguments:
                    return self._error(_mcp_error("INVALID_ARGUMENT", "community status accepts no arguments"))
                return self._result(community_status())
            if name == COMMUNITY_CALL_TOOL["name"]:
                command = arguments.get("command")
                params = arguments.get("params") or {}
                from scripts.community_bridge import call_community

                try:
                    return self._result(call_community(command, params))
                except CommunityBridgeError as error:
                    return self._error(_mcp_error(error.code, str(error)))
            return super().call_tool(name, arguments)

    return PluginMcpAdapter(**kwargs)
