"""Plugin-side MCP adapter: upstream runtime tools plus blender_auto_setup.

上游 vendored runtime 保持逐字不动；本模块以子类包装注入插件自有工具，
让首次使用的用户无需任何手动步骤即可建立 Blender MCP 连接。
"""

from __future__ import annotations

import time
from pathlib import Path

from scripts.auto_setup import run_auto_setup, wait_for_connection

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


def build_plugin_adapter(base_adapter_cls, *, plugin_root: Path | None = None, **kwargs):
    """Return a subclass instance of the vendored McpAdapter with blender_auto_setup added."""

    plugin_root = Path(plugin_root or Path(__file__).resolve().parents[1]).resolve()

    class PluginMcpAdapter(base_adapter_cls):
        _plugin_root = plugin_root

        def list_tools(self, *, cursor: str | None = None, limit: int = 50) -> dict:
            result = super().list_tools(cursor=cursor, limit=limit)
            tools = result.get("tools", [])
            if not any(tool.get("name") == AUTO_SETUP_TOOL["name"] for tool in tools):
                tools.append(dict(AUTO_SETUP_TOOL))
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
            return super().call_tool(name, arguments)

    return PluginMcpAdapter(**kwargs)
