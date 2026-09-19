"""First-run auto setup: install the Blender Add-on and connect without manual steps.

发现 Blender → 安装 PartMe Blender MCP Add-on → 持久启用 → 拉起 Blender 并自动
Start MCP Server。网络策略：优先拉取 GitHub Releases 上的最新 addon 包，网络
不可用或版本不新于内置时回退到 vendor/ 里 SHA-256 锁定的离线包。

纯标准库实现，禁止 import bpy：本模块运行在宿主 MCP server 进程，不在 Blender 内。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib import request as _urlrequest

DEFAULT_OUTPUT_ROOT = Path.home() / "partme" / "blender" / "design-outputs"
ADDON_MODULE = "partme_blender_mcp"
BLENDER_DOWNLOAD_URL = "https://www.blender.org/download/"
LATEST_RELEASE_API = (
    "https://api.github.com/repos/full-aigc-plugins/blender-mcp/releases/latest"
)
DOWNLOAD_TIMEOUT = 30
CLI_QUERY_TIMEOUT = 90


class AutoSetupError(RuntimeError):
    """Raised when auto setup cannot proceed and the caller must guide the user."""


# ---------------------------------------------------------------------------
# Blender discovery
# ---------------------------------------------------------------------------

def _candidate_blender_paths() -> list[Path]:
    candidates: list[Path] = []
    env = os.environ.get("PARTME_BLENDER_BIN")
    if env:
        candidates.append(Path(env))
    found = shutil.which("blender")
    if found:
        candidates.append(Path(found))
    home = Path.home()
    if sys.platform == "darwin":
        for root in (Path("/Applications"), home / "Applications"):
            candidates.append(root / "Blender.app/Contents/MacOS/Blender")
    elif sys.platform == "win32":
        program_dirs = [os.environ.get("ProgramFiles", r"C:\Program Files")]
        program_dirs.append(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        for base in program_dirs:
            for entry in Path(base).glob("Blender Foundation/Blender */blender.exe"):
                candidates.append(entry)
    else:
        candidates.extend(Path(p) for p in ("/snap/bin/blender", "/usr/local/bin/blender"))
    return candidates


def discover_blender() -> Path | None:
    for candidate in _candidate_blender_paths():
        if candidate.is_file():
            return candidate
    return None


def blender_running() -> bool:
    """Best-effort detection of a running GUI Blender; unknown state counts as running."""
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq blender.exe"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            return "blender.exe" in (out.stdout or "").lower()
        pattern = "Blender" if sys.platform == "darwin" else "blender"
        out = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True, timeout=15, check=False,
        )
        return bool((out.stdout or "").strip())
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Add-ons directory resolution
# ---------------------------------------------------------------------------

def _standard_script_roots() -> list[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library/Application Support/Blender Foundation/Blender"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "")) / "Blender Foundation/Blender"
    else:
        base = home / ".config/blender"
    if not base.is_dir():
        return []

    def version_key(path: Path) -> tuple:
        match = re.match(r"(\d+)\.(\d+)", path.name)
        return (int(match.group(1)), int(match.group(2))) if match else (0, 0)

    return sorted(
        (p / "scripts" for p in base.iterdir() if p.is_dir() and version_key(p) > (0, 0)),
        key=version_key,
        reverse=True,
    )


def scripts_root_via_cli(blender_bin: Path) -> Path | None:
    """Ask Blender itself for the per-version user scripts directory."""
    expression = (
        "import bpy; print('PARTME_SCRIPTS=' + bpy.utils.user_resource('SCRIPTS'))"
    )
    try:
        out = subprocess.run(
            [str(blender_bin), "--background", "--factory-startup", "--python-expr", expression],
            capture_output=True, text=True, timeout=CLI_QUERY_TIMEOUT, check=False,
        )
    except Exception:
        return None
    for line in (out.stdout or "").splitlines():
        if line.startswith("PARTME_SCRIPTS="):
            return Path(line.split("=", 1)[1].strip())
    return None


def resolve_scripts_root(blender_bin: Path | None) -> Path:
    roots: list[Path] = []
    if blender_bin is not None:
        via_cli = scripts_root_via_cli(blender_bin)
        if via_cli is not None:
            roots.append(via_cli)
    roots.extend(_standard_script_roots())
    if not roots:
        raise AutoSetupError(
            "未能定位 Blender 的用户脚本目录；请先启动一次 Blender 再重试，"
            f"或手动安装：{BLENDER_DOWNLOAD_URL}"
        )
    return roots[0] / "addons"


# ---------------------------------------------------------------------------
# Add-on package resolution: online latest first, bundled lock as fallback
# ---------------------------------------------------------------------------

def _lock_data(plugin_root: Path) -> dict:
    from scripts.partme_runtime import _load_lock

    return _load_lock(Path(plugin_root))


def _version_tuple(text: str) -> tuple:
    match = re.search(r"(\d+(?:\.\d+)+)", text or "")
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def bundled_addon_zip(plugin_root: Path) -> Path:
    from scripts.partme_runtime import locked_artifact

    path, _lock = locked_artifact(Path(plugin_root), "addon")
    return path


def _release_payload() -> dict | None:
    try:
        req = _urlrequest.Request(
            LATEST_RELEASE_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "partme-blender-design"},
        )
        with _urlrequest.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def resolve_addon_zip(plugin_root: Path) -> tuple[Path, str]:
    """Return (zip_path, source_description); online latest wins, bundled zip is the fallback."""
    bundled = bundled_addon_zip(Path(plugin_root))
    lock = _lock_data(Path(plugin_root))
    bundled_version = str(lock.get("version", ""))

    release = _release_payload()
    if release:
        tag = str(release.get("tag_name", ""))
        if _version_tuple(tag) > _version_tuple(bundled_version):
            for asset in release.get("assets", []):
                name = str(asset.get("name", ""))
                if name.startswith("partme-blender-mcp-addon-") and name.endswith(".zip"):
                    try:
                        req = _urlrequest.Request(
                            str(asset.get("browser_download_url", "")),
                            headers={"User-Agent": "partme-blender-design"},
                        )
                        with _urlrequest.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as response:
                            data = response.read()
                        probe = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
                        probe.write(data)
                        probe.close()
                        with zipfile.ZipFile(probe.name) as archive:
                            archive.namelist()
                        return Path(probe.name), f"github-release {tag}"
                    except Exception:
                        break
    return bundled, f"bundled v{bundled_version}"


# ---------------------------------------------------------------------------
# Install / enable / auto-start
# ---------------------------------------------------------------------------

def install_addon(addons_dir: Path, zip_path: Path) -> Path:
    target = addons_dir / ADDON_MODULE
    staging = Path(tempfile.mkdtemp(prefix="partme-addon-install-"))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(staging)
        packages = [p for p in staging.iterdir() if p.is_dir() and p.name == ADDON_MODULE]
        if not packages:
            raise AutoSetupError("addon 包中未找到 partme_blender_mcp 模块，文件可能已损坏")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(packages[0], target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


def enable_addon_persistently(blender_bin: Path, module: str = ADDON_MODULE) -> bool:
    expression = (
        "import addon_utils, bpy\n"
        f"addon_utils.enable({module!r}, default_set=True, persistent=True)\n"
        "bpy.ops.wm.save_userpref()\n"
        "mods = {m.__name__: enabled for m, enabled in addon_utils.modules_ref()}\n"
        f"print('PARTME_ENABLED=' + str({module!r} in mods and mods[{module!r}]))\n"
    )
    out = subprocess.run(
        [str(blender_bin), "--background", "--python-expr", expression],
        capture_output=True, text=True, timeout=CLI_QUERY_TIMEOUT, check=False,
    )
    return "PARTME_ENABLED=True" in (out.stdout or "")


def autostart_expression(output_root: Path) -> str:
    root = str(output_root).replace("\\", "\\\\").replace("'", "\\'")
    return (
        "import bpy\n"
        "def _partme_autostart():\n"
        f"    bpy.context.scene.partme_blender_output_root = '{root}'\n"
        "    try:\n"
        "        bpy.ops.partme_blender.start_connector()\n"
        "        print('PARTME_AUTOSTART_OK')\n"
        "    except Exception as error:\n"
        "        print('PARTME_AUTOSTART_ERROR', error)\n"
        "    return None\n"
        "bpy.app.timers.register(_partme_autostart, first_interval=2.0)\n"
    )


def launch_connected(blender_bin: Path, output_root: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [str(blender_bin), "--python-expr", autostart_expression(output_root)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_auto_setup(
    plugin_root: Path,
    *,
    output_root: Path | None = None,
    launch_blender: bool = True,
) -> dict:
    plugin_root = Path(plugin_root).resolve()
    output_root = Path(output_root or os.environ.get("PARTME_BLENDER_OUTPUT_ROOT") or DEFAULT_OUTPUT_ROOT)
    steps: list[dict] = []

    blender_bin = discover_blender()
    steps.append({"step": "discover", "ok": blender_bin is not None, "detail": str(blender_bin or BLENDER_DOWNLOAD_URL)})
    if blender_bin is None:
        return {
            "ok": False,
            "stage": "discover",
            "steps": steps,
            "connected": False,
            "manualHint": f"尚未安装 Blender。请先从官网下载安装：{BLENDER_DOWNLOAD_URL} ，装好后重新运行 blender_auto_setup。",
        }

    running = blender_running()
    steps.append({"step": "detect-running", "ok": True, "detail": "Blender 正在运行" if running else "Blender 未运行"})

    output_root.mkdir(parents=True, exist_ok=True)
    steps.append({"step": "output-root", "ok": True, "detail": str(output_root)})

    zip_path, source = resolve_addon_zip(plugin_root)
    steps.append({"step": "resolve-addon", "ok": True, "detail": source})

    try:
        addons_dir = resolve_scripts_root(blender_bin)
        installed = install_addon(addons_dir, zip_path)
        steps.append({"step": "install", "ok": True, "detail": str(installed)})
    except AutoSetupError as error:
        steps.append({"step": "install", "ok": False, "detail": str(error)})
        return {"ok": False, "stage": "install", "steps": steps, "connected": False, "manualHint": str(error)}

    if running:
        return {
            "ok": False,
            "stage": "enable",
            "steps": steps,
            "connected": False,
            "manualHint": (
                "检测到 Blender 正在运行，无法对运行中的实例自动启用插件。"
                "请完全退出 Blender（Cmd/Alt+F4），然后重新运行 blender_auto_setup，"
                "我们会自动启用并连接；或手动在 偏好设置 > 插件 中启用 PartMe Blender MCP，"
                "并在 N 面板点击 Start MCP Server。"
            ),
        }

    enabled = enable_addon_persistently(blender_bin)
    steps.append({"step": "enable", "ok": enabled, "detail": "已持久启用" if enabled else "启用结果未知（将尝试继续）"})

    launched = None
    if launch_blender:
        launched = launch_connected(blender_bin, output_root)
        steps.append({"step": "launch", "ok": launched.pid > 0, "detail": f"pid={launched.pid}"})

    return {
        "ok": True,
        "stage": "launch" if launched else "enable",
        "steps": steps,
        "connected": False,
        "outputRoot": str(output_root),
        "addonSource": source,
        "blender": str(blender_bin),
        "launchedPid": launched.pid if launched else None,
        "manualHint": None if launched else "请手动打开 Blender，连接会在启动数秒后自动建立。",
    }


def wait_for_connection(attempt, *, seconds: int = 20, interval: float = 1.5) -> dict | None:
    """Poll `attempt()` until it stops raising or the budget runs out."""
    deadline = time.monotonic() + max(0, seconds)
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return attempt()
        except Exception as error:  # noqa: BLE001 - probe until ready
            last_error = error
            time.sleep(interval)
    if last_error is not None:
        raise last_error
    return None
