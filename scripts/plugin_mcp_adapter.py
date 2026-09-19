"""Plugin-side MCP adapter: upstream runtime tools plus blender_auto_setup.

上游 vendored runtime 保持逐字不动；本模块以子类包装注入插件自有工具，
让首次使用的用户无需任何手动步骤即可建立 Blender MCP 连接。
"""

from __future__ import annotations

import time
from pathlib import Path

from scripts.auto_setup import run_auto_setup, wait_for_connection
from scripts.community_bridge import (
    COMMUNITY_COMMANDS, PROVIDERS, CommunityBridgeError, command_risk, community_status,
)


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
        "List every 3D-asset provider this plugin can drive: the vendored community Add-on "
        f"({_PROVIDER_LIST}) inside Blender on port 9876, plus the plugin's own guarded native "
        "asset commands (asset.library, asset.polypizza_*, asset.fetch_url, asset.fetch_generated, asset.import_file, "
        "asset.pack_resources). The community "
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
        "(Sketchfab / Hyper3D / Hunyuan3D) are user-supplied in the community Add-on's Blender "
        "preferences; PolyHaven needs no key. Paid generation and external export require local "
        "approval. Community download/import commands are intentionally excluded: stage files "
        "through PartMe asset commands and import in a separate transaction."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "enum": sorted(COMMUNITY_COMMANDS), "description": "Community command name"},
            "params": {"type": "object", "description": "Command parameters as defined by the community Add-on"},
            "_requestId": {"type": "string", "minLength": 1},
            "_transactionId": {"type": "string", "minLength": 1},
            "_expectedSceneRevision": {"type": "integer", "minimum": 0},
        },
        "required": ["command"],
        "additionalProperties": False,
    },
    "outputSchema": {"type": "object"},
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
}

PROVIDER_TASKS_TOOL = {
    "name": "blender_provider_tasks",
    "title": "Inspect active asset and AI provider tasks",
    "description": (
        "Read the provider-neutral task state shown in the PartMe Blender MCP sidebar, including "
        "progress and a user-requested local cancellation. A cancelled task must not be polled, "
        "downloaded or imported again."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "providerId": {"type": "string"},
            "taskId": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "outputSchema": {"type": "object"},
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
}

_CREATE_GENERATION_COMMANDS = {
    "create_rodin_job": "hyper3d",
    "create_hunyuan_job": "hunyuan3d",
}
_POLL_GENERATION_COMMANDS = {
    "poll_rodin_job_status": "hyper3d",
    "poll_hunyuan_job_status": "hunyuan3d",
}
_TASK_ID_KEYS = ("subscription_key", "request_id", "job_id", "JobId", "uuid", "id")


def _find_task_id(payload) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in _TASK_ID_KEYS:
        value = payload.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    for value in payload.values():
        nested = _find_task_id(value)
        if nested:
            return nested
    return None


def _find_scalar(payload, keys):
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if key in payload:
            return payload[key]
    for value in payload.values():
        found = _find_scalar(value, keys)
        if found is not None:
            return found
    return None


def _generation_state(payload: dict) -> tuple[str, float | None, str]:
    if payload.get("error"):
        return "failed", None, "生成失败"
    statuses = payload.get("status_list")
    if isinstance(statuses, list) and statuses:
        raw_status = " ".join(str(value) for value in statuses)
    else:
        raw_status = str(_find_scalar(payload, ("status", "state", "Status", "State")) or "")
    normalized = raw_status.upper()
    if any(token in normalized for token in ("FAIL", "ERROR", "REJECT")):
        state, stage = "failed", "生成失败"
    elif any(token in normalized for token in ("COMPLETE", "SUCCEED", "SUCCESS", "DONE", "FINISH")):
        state, stage = "completed", "生成完成"
    elif "QUEUE" in normalized or "SUBMIT" in normalized:
        state, stage = "submitting", "等待供应商处理"
    else:
        state, stage = "generating", "正在轮询结果"
    raw_progress = _find_scalar(payload, ("progress", "Progress", "percentage", "percent"))
    progress = None
    if isinstance(raw_progress, (int, float)) and not isinstance(raw_progress, bool):
        progress = float(raw_progress)
        if progress > 1:
            progress /= 100
        progress = min(1.0, max(0.0, progress))
    if state == "completed":
        progress = 1.0
    return state, progress, stage


def build_plugin_adapter(base_adapter_cls, *, plugin_root: Path | None = None, **kwargs):
    """Return a subclass instance of the vendored McpAdapter with blender_auto_setup added."""

    plugin_root = Path(plugin_root or Path(__file__).resolve().parents[1]).resolve()

    class PluginMcpAdapter(base_adapter_cls):
        _plugin_root = plugin_root

        def _provider_task_control(self, payload: dict):
            """Best-effort bridge to the runtime task protocol; old runtimes keep working."""
            try:
                response = self._active_bridge().call("provider.task_control", payload)
            except Exception:  # noqa: BLE001 - compatibility with the previous pinned runtime
                return None
            if not isinstance(response, dict) or response.get("status") == "failed" or "error" in response:
                return None
            result = response.get("result")
            return result if isinstance(result, dict) else None

        def _cancelled_task(self, provider_id: str, task_id: str | None):
            if not task_id:
                return None
            task = self._provider_task_control({
                "operation": "status", "providerId": provider_id, "taskId": task_id,
            })
            if task and (task.get("cancelRequested") or task.get("state") == "cancelled"):
                return task
            return None

        def _report_generation(self, command: str, params: dict, result: dict, request_id: str | None = None):
            provider_id = _CREATE_GENERATION_COMMANDS.get(command) or _POLL_GENERATION_COMMANDS.get(command)
            if provider_id is None:
                return None
            task_id = _find_task_id(result) or _find_task_id(params) or request_id
            if not task_id:
                return None
            if command in _CREATE_GENERATION_COMMANDS:
                state, progress, stage = ("failed", None, "生成失败") if result.get("error") else (
                    "generating", 0.0, "已提交 · 等待生成",
                )
            else:
                state, progress, stage = _generation_state(result)
            operation = "finish" if state in {"completed", "failed", "cancelled"} else (
                "start" if command in _CREATE_GENERATION_COMMANDS else "update"
            )
            payload = {
                "operation": operation,
                "providerId": provider_id,
                "taskId": task_id,
                "state": state,
                "stage": stage,
                "statusText": f"生成中 {progress:.0%}" if progress is not None and state not in {"completed", "failed"} else stage,
                "cancelSupported": False,
            }
            if progress is not None:
                payload["progress"] = progress
            if result.get("error"):
                payload["message"] = str(result["error"])[:512]
            task = self._provider_task_control(payload)
            if task is not None or command in _CREATE_GENERATION_COMMANDS:
                return task

            # Blender can be restarted while a community generation keeps running.
            # Recreate the provider-neutral task so polling resumes in the UI instead
            # of silently losing progress after the in-memory registry was cleared.
            recovery = dict(payload)
            if operation == "finish":
                recovery.update({
                    "operation": "start",
                    "state": "generating",
                    "stage": "已恢复供应商任务",
                    "statusText": "已恢复 · 正在同步最终结果",
                    "progress": min(progress or 0.0, 0.99),
                })
                task = self._provider_task_control(recovery)
                if task is not None:
                    return self._provider_task_control(payload)
                return None
            recovery["operation"] = "start"
            return self._provider_task_control(recovery)

        def list_tools(self, *, cursor: str | None = None, limit: int = 50) -> dict:
            catalog = list(self.tools)
            known = {tool.get("name") for tool in catalog}
            catalog.extend(dict(extra) for extra in (
                AUTO_SETUP_TOOL, COMMUNITY_STATUS_TOOL, COMMUNITY_CALL_TOOL, PROVIDER_TASKS_TOOL,
            )
                           if extra["name"] not in known)
            if cursor is None:
                offset = 0
            elif isinstance(cursor, str) and cursor.startswith("offset:") and cursor[7:].isdigit():
                offset = int(cursor[7:])
            else:
                raise _mcp_error("INVALID_CURSOR", "tools/list cursor is invalid")
            if offset < 0 or offset > len(catalog):
                raise _mcp_error("INVALID_CURSOR", "tools/list cursor is out of range")
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 100:
                raise _mcp_error("INVALID_ARGUMENT", "tools/list limit must be an integer from 1 to 100")
            result = {"tools": catalog[offset:offset + limit]}
            if offset + limit < len(catalog):
                result["nextCursor"] = f"offset:{offset + limit}"
            return result

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
            if name == PROVIDER_TASKS_TOOL["name"]:
                arguments = dict(arguments or {})
                unknown = sorted(set(arguments) - set(PROVIDER_TASKS_TOOL["inputSchema"]["properties"]))
                if unknown:
                    return self._error(_mcp_error("INVALID_ARGUMENT", f"unknown fields: {unknown}"))
                provider_id = arguments.get("providerId")
                task_id = arguments.get("taskId")
                if task_id and not provider_id:
                    return self._error(_mcp_error("INVALID_ARGUMENT", "taskId requires providerId"))
                payload = {"operation": "status" if provider_id else "list"}
                if provider_id:
                    payload["providerId"] = provider_id
                if task_id:
                    payload["taskId"] = task_id
                result = self._provider_task_control(payload)
                if result is None:
                    return self._error(_mcp_error("PROVIDER_TASKS_UNAVAILABLE", "provider task state is unavailable"))
                return self._result(result)
            if name == COMMUNITY_CALL_TOOL["name"]:
                arguments = dict(arguments or {})
                command = arguments.get("command")
                params = arguments.get("params") or {}
                from scripts.community_bridge import call_community

                try:
                    provider_id = _POLL_GENERATION_COMMANDS.get(command)
                    task_id = _find_task_id(params)
                    cancelled = self._cancelled_task(provider_id, task_id) if provider_id else None
                    if cancelled:
                        return self._result({
                            "status": "cancelled",
                            "providerId": provider_id,
                            "taskId": task_id,
                            "remoteMayContinue": bool(cancelled.get("remoteMayContinue")),
                            "message": cancelled.get("message") or "生成任务已由用户终止",
                        })
                    risk = command_risk(command)
                    if risk != "read":
                        request_id = arguments.get("_requestId")
                        transaction_id = arguments.get("_transactionId")
                        if not request_id or not transaction_id:
                            return self._error(_mcp_error(
                                "INVALID_ARGUMENT",
                                "gated community actions require _requestId and _transactionId",
                            ))
                        gate = self._active_bridge().call(
                            "provider.external_action",
                            {"providerId": COMMUNITY_COMMANDS[command], "action": command, "risk": risk},
                            request_id=request_id,
                            transaction_id=transaction_id,
                            expected_scene_revision=arguments.get("_expectedSceneRevision"),
                        )
                        if isinstance(gate, dict) and (gate.get("status") == "failed" or "error" in gate):
                            return self._result(gate, is_error=True)
                    result = call_community(command, params)
                    task = self._report_generation(command, params, result, arguments.get("_requestId"))
                    if task is not None:
                        result = dict(result)
                        result["_partmeTask"] = task
                    return self._result(result, is_error=bool(result.get("error")))
                except CommunityBridgeError as error:
                    return self._error(_mcp_error(error.code, str(error)))
            return super().call_tool(name, arguments)

    return PluginMcpAdapter(**kwargs)
