"""Bridge from the plugin MCP adapter to the vendored community Add-on (localhost:9876).

社区 Add-on（blender_mcp_community，MIT，ahujasid/blender-mcp v2.0.0 verbatim）在
Blender 内监听 TCP 9876，收发 JSON：{"type": <command>, "params": {...}} ->
{"status": "success", "result": ...}。本模块是该协议的宿主侧客户端 + 命令白名单。

白名单按供应商分组（注册表结构）：新增 3D 平台 = 社区 addon 升级 + 在此登记命令，
MCP 工具面（blender_community_call）无需改动。
"""

from __future__ import annotations

import json
import socket

COMMUNITY_HOST = "127.0.0.1"
COMMUNITY_PORT = 9876
RECV_TIMEOUT = 120.0

# 命令白名单：基础面 + 各资产供应商面（与社区 addon 的 handlers 分发表一一对应）。
COMMUNITY_COMMANDS: dict[str, str] = {
    # base
    "ping": "base",
    "get_scene_info": "base",
    "get_world_state_snapshot": "base",
    "get_addon_info": "base",
    "get_object_info": "base",
    "get_viewport_screenshot": "base",
    "describe_node_type": "base",
    "bpy_api_lookup": "base",
    "export_scene": "base",
    # polyhaven
    "get_polyhaven_status": "polyhaven",
    "get_polyhaven_categories": "polyhaven",
    "search_polyhaven_assets": "polyhaven",
    # sketchfab
    "get_sketchfab_status": "sketchfab",
    "search_sketchfab_models": "sketchfab",
    "get_sketchfab_model_preview": "sketchfab",
    # hyper3d rodin
    "get_hyper3d_status": "hyper3d",
    "create_rodin_job": "hyper3d",
    "poll_rodin_job_status": "hyper3d",
    # hunyuan3d
    "get_hunyuan3d_status": "hunyuan3d",
    "create_hunyuan_job": "hunyuan3d",
    "poll_hunyuan_job_status": "hunyuan3d",
}

# These resolver calls may contain short-lived signed download URLs. They are
# available only to plugin-side orchestration and are never exposed through
# blender_community_call or its public enum.
INTERNAL_COMMUNITY_COMMANDS: dict[str, str] = {
    "resolve_sketchfab_download": "sketchfab",
    "resolve_rodin_asset": "hyper3d",
}

PROVIDERS = ["base", "polyhaven", "sketchfab", "hyper3d", "hunyuan3d"]

# 社区实现中会直接下载或改写场景的命令不再公开。下载结果先由 PartMe
# `asset.fetch_url` / `asset.fetch_generated` 写入授权目录，再单独调用 `asset.import_file`。
BLOCKED_COMMUNITY_COMMANDS = {
    "download_polyhaven_asset", "set_texture", "download_sketchfab_model",
    "get_polypizza_status", "search_polypizza_models", "download_polypizza_model",
    "import_generated_asset", "import_generated_asset_hunyuan",
}

COMMUNITY_COMMAND_RISKS = {
    **{command: "read" for command in COMMUNITY_COMMANDS},
    "export_scene": "external_export",
    "create_rodin_job": "paid_generation",
    "create_hunyuan_job": "paid_generation",
}


def command_risk(command: str) -> str:
    return COMMUNITY_COMMAND_RISKS.get(command, "read")

# 插件自有 Harness 的资产命令面（不经 9876，走受控 MCP 工具，密钥用环境变量）。
NATIVE_ASSET_COMMANDS = {
    "asset.library": "manage the approved asset library",
    "asset.polypizza_search": "search Poly Pizza (POLYPIZZA_API_KEY env)",
    "asset.polypizza_download": "download a Poly Pizza model (POLYPIZZA_API_KEY env)",
    "asset.fetch_url": "fetch an asset from any approved URL into the scene",
    "asset.fetch_generated": "stage an approved AI result before importing it",
    "asset.import_file": "import a local file under approved asset roots",
    "asset.pack_resources": "pack external resources into the .blend",
    "asset.make_paths_relative": "make asset paths relative for portable scenes",
}


class CommunityBridgeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def call_community(command: str, params: dict | None = None, *, host: str | None = None,
                   port: int | None = None, timeout: float | None = None,
                   allow_internal: bool = False) -> dict:
    """Send one JSON command to the community Add-on and return its result payload."""
    host = host or COMMUNITY_HOST
    port = COMMUNITY_PORT if port is None else port
    timeout = RECV_TIMEOUT if timeout is None else timeout
    allowed = command in COMMUNITY_COMMANDS or (allow_internal and command in INTERNAL_COMMUNITY_COMMANDS)
    if not allowed:
        if command in BLOCKED_COMMUNITY_COMMANDS:
            raise CommunityBridgeError(
                "COMMUNITY_COMMAND_REQUIRES_PARTME_FLOW",
                f"{command} bypasses the PartMe approval/import boundary; stage with "
                "asset.fetch_url or asset.fetch_generated, then import with asset.import_file",
            )
        raise CommunityBridgeError(
            "UNKNOWN_COMMAND",
            f"community command not in allowlist: {command}",
        )
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise CommunityBridgeError("INVALID_ARGUMENT", "params must be an object")
    payload = json.dumps({"type": command, "params": params})
    try:
        with socket.create_connection((host, port), timeout=min(timeout, 20.0)) as sock:
            sock.settimeout(timeout)
            sock.sendall((payload + "\n").encode("utf-8"))
            chunks = bytearray()
            while not chunks.endswith(b"\n"):
                block = sock.recv(65536)
                if not block:
                    break
                chunks.extend(block)
    except OSError as error:
        raise CommunityBridgeError(
            "COMMUNITY_ADDON_UNREACHABLE",
            f"community Add-on unreachable on {host}:{port} — is Blender running with "
            "blender_mcp_community enabled (auto_setup installs and enables it): {error}",
        ) from error
    text = chunks.decode("utf-8", "replace").strip()
    if not text:
        raise CommunityBridgeError("EMPTY_RESPONSE", "community Add-on returned no data")
    try:
        envelope = json.loads(text)
    except json.JSONDecodeError as error:
        raise CommunityBridgeError("BAD_RESPONSE", f"community Add-on returned invalid JSON: {text[:200]}") from error
    if envelope.get("status") != "success":
        raise CommunityBridgeError(
            "COMMUNITY_COMMAND_FAILED",
            str(envelope.get("message") or envelope),
        )
    result = envelope.get("result")
    return result if isinstance(result, dict) else {"result": result}


def community_status() -> dict:
    """Ping + capability handshake; degrades to a structured error when unreachable."""
    try:
        pong = call_community("ping", {}, timeout=5.0)
    except CommunityBridgeError as error:
        return {"connected": False, "error": error.code, "message": str(error)}
    info = call_community("get_addon_info", {}, timeout=10.0)
    return {
        "connected": bool(pong.get("pong")),
        "addon": info.get("name"),
        "addonVersion": ".".join(str(part) for part in info.get("addon_version", [])),
        "protocolVersion": info.get("protocol_version"),
        "providers": {
            provider: sorted(cmd for cmd, group in COMMUNITY_COMMANDS.items() if group == provider)
            for provider in PROVIDERS if provider != "base"
        },
        "port": COMMUNITY_PORT,
        "native": {
            "description": "PartMe guarded asset commands served by this plugin's own MCP tools "
                           "(no community Add-on needed; keys via environment variables)",
            "tools": {f"blender_{cmd.replace('.', '_')}": desc for cmd, desc in NATIVE_ASSET_COMMANDS.items()},
        },
    }
