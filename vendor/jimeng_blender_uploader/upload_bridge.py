"""Bridge between Blender and the local Jimeng/Dreamina import helper."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import base64
import http.server
import secrets
import threading
import time
import urllib.parse


class UploadError(RuntimeError):
    pass


STANDARD_BIN_DIRS = (
    "/usr/local/bin",
    "/opt/homebrew/bin",
    "/usr/bin",
    os.path.expanduser("~/.nvm/current/bin"),
    os.path.expanduser("~/.volta/bin"),
)


def package_root():
    return os.path.dirname(os.path.abspath(__file__))


def helper_script():
    return os.path.join(package_root(), "helpers", "jimeng_upload", "local_bridge.js")


def helper_dir():
    return os.path.dirname(helper_script())


_LOCAL_BRIDGES = []
DEFAULT_FFMPEG_TIMEOUT_SECONDS = 15 * 60
MAX_FFMPEG_ERROR_CHARS = 4000
DEFAULT_TARGET_URL = "https://jimeng.jianying.com/ai-tool/home"
DEFAULT_TTL_SECONDS = 30 * 60
DEFAULT_CLOSE_AFTER_DOWNLOAD_SECONDS = 60


def _runtime_root():
    return os.path.join(package_root(), "runtime", "ffmpeg")


def _bundled_ffmpeg_candidates():
    root = _runtime_root()
    if sys.platform.startswith("win"):
        machine = platform.machine().lower()
        if sys.maxsize <= 2**32:
            names = ("windows-x86", "windows-x86_64", "windows-arm64")
        elif machine in ("arm64", "aarch64"):
            names = ("windows-arm64", "windows-x86_64", "windows-x86")
        else:
            names = ("windows-x86_64", "windows-x86", "windows-arm64")
        return [os.path.join(root, name, "ffmpeg.exe") for name in names]
    if sys.platform == "darwin":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            names = ("macos-aarch64", "macos-x86_64")
        else:
            names = ("macos-x86_64", "macos-aarch64")
        return [os.path.join(root, name, "ffmpeg") for name in names]
    return []


def _prepare_bundled_executable(path):
    if not path or not os.path.exists(path):
        return False
    if not sys.platform.startswith("win"):
        try:
            os.chmod(path, os.stat(path).st_mode | 0o755)
        except Exception:
            pass
    if sys.platform == "darwin":
        try:
            subprocess.run(
                ["xattr", "-d", "com.apple.quarantine", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass
    return os.path.exists(path) and (sys.platform.startswith("win") or os.access(path, os.X_OK))


def subprocess_env():
    env = os.environ.copy()
    existing = env.get("PATH", "")
    parts = [item for item in STANDARD_BIN_DIRS if item and os.path.isdir(item)]
    env["PATH"] = os.pathsep.join(parts + ([existing] if existing else []))
    return env


def _ffmpeg_candidates():
    candidates = list(_bundled_ffmpeg_candidates())
    env_ffmpeg = os.environ.get("JIMENG_UPLOADER_FFMPEG")
    if env_ffmpeg:
        candidates.append(env_ffmpeg)

    found = shutil.which("ffmpeg", path=subprocess_env().get("PATH"))
    if found:
        candidates.append(found)

    candidates.extend(("/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/bin/ffmpeg"))
    if sys.platform.startswith("win"):
        roots = [
            os.environ.get("ProgramFiles", ""),
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        candidates.extend(os.path.join(root, "ffmpeg", "bin", "ffmpeg.exe") for root in roots if root)

    unique = []
    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        key = os.path.normcase(os.path.abspath(candidate))
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _is_bundled_ffmpeg(path):
    try:
        runtime_root = os.path.normcase(os.path.abspath(_runtime_root()))
        candidate = os.path.normcase(os.path.abspath(path))
        return os.path.commonpath((runtime_root, candidate)) == runtime_root
    except (OSError, ValueError):
        return False


def _ffmpeg_candidate_available(path, repair=False):
    if repair and _is_bundled_ffmpeg(path):
        return _prepare_bundled_executable(path)
    if not path or not os.path.exists(path):
        return False
    return sys.platform.startswith("win") or os.access(path, os.X_OK)


def _remove_partial_output(output_path):
    if not output_path:
        return
    try:
        if os.path.exists(output_path):
            os.unlink(output_path)
    except OSError:
        pass


def _process_error_text(output):
    if isinstance(output, bytes):
        output = output.decode("utf-8", "replace")
    text = str(output or "").strip()
    if len(text) > MAX_FFMPEG_ERROR_CHARS:
        text = "..." + text[-MAX_FFMPEG_ERROR_CHARS:]
    return text


def run_ffmpeg(arguments, output_path=None, timeout_seconds=None):
    """Run ffmpeg lazily, falling back to every usable bundled/system candidate."""
    timeout = float(timeout_seconds or DEFAULT_FFMPEG_TIMEOUT_SECONDS)
    failures = []
    attempted = []

    for candidate in _ffmpeg_candidates():
        if not _ffmpeg_candidate_available(candidate, repair=True):
            continue

        ffmpeg = os.path.abspath(candidate)
        attempted.append(ffmpeg)
        _remove_partial_output(output_path)
        command = [ffmpeg] + list(arguments)
        try:
            subprocess.check_output(
                command,
                cwd=helper_dir(),
                env=subprocess_env(),
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            detail = _process_error_text(getattr(exc, "output", None))
            reason = "timed out after {0:g} seconds".format(timeout)
            if detail:
                reason = "{0}: {1}".format(reason, detail)
            failures.append("{0}: {1}".format(ffmpeg, reason))
            _remove_partial_output(output_path)
            continue
        except subprocess.CalledProcessError as exc:
            detail = _process_error_text(exc.output) or "exit code {0}".format(exc.returncode)
            failures.append("{0}: {1}".format(ffmpeg, detail))
            _remove_partial_output(output_path)
            continue
        except OSError as exc:
            failures.append("{0}: {1}".format(ffmpeg, exc))
            _remove_partial_output(output_path)
            continue

        if output_path and (
            not os.path.exists(output_path) or os.path.getsize(output_path) <= 0
        ):
            failures.append("{0}: did not create a valid output file".format(ffmpeg))
            _remove_partial_output(output_path)
            continue

        return ffmpeg

    if not attempted:
        raise UploadError(
            "No usable ffmpeg executable was found in the bundled runtime or system fallbacks."
        )
    raise UploadError(
        "All available ffmpeg executables failed.\n{0}".format("\n".join(failures))
    )


def _base64_url(value):
    data = value.encode("utf-8") if isinstance(value, str) else value
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _allowed_origin(origin):
    if not origin:
        return False
    try:
        parsed = urllib.parse.urlparse(origin)
    except Exception:
        return False
    host = parsed.hostname or ""
    if parsed.scheme == "https" and (
        host == "jimeng.jianying.com"
        or host.endswith(".jianying.com")
        or host == "dreamina.capcut.com"
        or host.endswith(".capcut.com")
    ):
        return True
    return parsed.scheme in ("http", "https") and host in ("localhost", "127.0.0.1", "::1")


def _content_disposition(video_path):
    filename = os.path.basename(video_path or "blender-render.mp4").replace("\r", "_").replace("\n", "_")
    fallback = "".join(ch if 0x20 <= ord(ch) <= 0x7E and ch != '"' else "_" for ch in filename)
    encoded = urllib.parse.quote(filename)
    return "inline; filename=\"{0}\"; filename*=UTF-8''{1}".format(fallback, encoded)


def _make_redirect_url(target_url, resource_info_url):
    parsed = urllib.parse.urlparse(target_url or DEFAULT_TARGET_URL)
    path = "/ai-tool/home" if parsed.path.rstrip("/") == "/ai-tool" else parsed.path
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key not in ("channel", "thirdparty_id")]
    query.extend(
        [
            ("channel", "blender"),
            ("thirdparty_id", _base64_url(resource_info_url)),
        ]
    )
    return urllib.parse.urlunparse(parsed._replace(path=path, query=urllib.parse.urlencode(query)))


def _start_python_bridge(video_path, prompt, target_url):
    token = secrets.token_urlsafe(24)
    ttl_seconds = float(os.environ.get("JIMENG_LOCAL_BRIDGE_TTL_MS") or 0) / 1000.0
    if ttl_seconds <= 0:
        ttl_seconds = DEFAULT_TTL_SECONDS
    close_after_download_seconds = float(
        os.environ.get("JIMENG_LOCAL_BRIDGE_CLOSE_AFTER_DOWNLOAD_MS") or 0
    ) / 1000.0
    if close_after_download_seconds <= 0:
        close_after_download_seconds = DEFAULT_CLOSE_AFTER_DOWNLOAD_SECONDS
    expires_at = time.time() + ttl_seconds
    prompt_text = prompt or ""

    class LocalBridgeHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, _format, *args):
            return

        def _write_cors(self):
            origin = self.headers.get("Origin", "")
            if _allowed_origin(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")

        def _send_json(self, status_code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self._write_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self._write_cors()
            self.end_headers()

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path or "")
            query = urllib.parse.parse_qs(parsed.query)
            if (query.get("token") or [""])[0] != token:
                self._send_json(403, {"status": "failed", "code": "INVALID_TOKEN"})
                return
            if time.time() > expires_at:
                self._send_json(410, {"status": "failed", "code": "TOKEN_EXPIRED"})
                self.server.schedule_shutdown(0)
                return
            if parsed.path in ("/resouce_info", "/resource_info"):
                port = int(getattr(self.server, "server_port", 0) or 0)
                self._send_json(
                    200,
                    {
                        "file_url": "http://127.0.0.1:{0}/file?token={1}".format(
                            port,
                            urllib.parse.quote(token),
                        ),
                        "prompt": prompt_text,
                    },
                )
                return
            if parsed.path != "/file":
                self._send_json(404, {"status": "failed", "code": "NOT_FOUND"})
                return
            if not os.path.exists(video_path):
                self._send_json(404, {"status": "failed", "code": "FILE_NOT_FOUND"})
                return

            self.send_response(200)
            self._write_cors()
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(os.path.getsize(video_path)))
            self.send_header("Content-Disposition", _content_disposition(video_path))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with open(video_path, "rb") as fh:
                shutil.copyfileobj(fh, self.wfile)
            self.server.schedule_shutdown(close_after_download_seconds)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LocalBridgeHandler)
    shutdown_timer = {"timer": None}

    def schedule_shutdown(delay_seconds):
        timer = shutdown_timer.get("timer")
        if timer:
            timer.cancel()

        def close_server():
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
            try:
                _LOCAL_BRIDGES.remove(server)
            except ValueError:
                pass

        next_timer = threading.Timer(max(0.0, float(delay_seconds)), close_server)
        next_timer.daemon = True
        shutdown_timer["timer"] = next_timer
        next_timer.start()

    server.schedule_shutdown = schedule_shutdown
    _LOCAL_BRIDGES.append(server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    schedule_shutdown(ttl_seconds)

    port = int(server.server_port)
    resource_info_url = "http://127.0.0.1:{0}/resouce_info?token={1}".format(
        port,
        urllib.parse.quote(token),
    )
    return {
        "status": "ready",
        "port": port,
        "pid": os.getpid(),
        "helper_pid": os.getpid(),
        "resource_info_url": resource_info_url,
        "redirect_url": _make_redirect_url(target_url, resource_info_url),
        "expires_at": int(expires_at * 1000),
        "video": video_path,
    }


def standardize_mp4(source_path, force=False):
    source_path = os.path.abspath(source_path)
    root, ext = os.path.splitext(source_path)
    if ext.lower() == ".mp4" and not force:
        return source_path

    target_path = root + "_jimeng_upload.mp4"
    arguments = [
        "-y",
        "-i",
        source_path,
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2:out_range=tv,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-color_range",
        "tv",
        "-tag:v",
        "avc1",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        target_path,
    ]
    run_ffmpeg(arguments, output_path=target_path)
    return target_path


def _startup_kwargs():
    if sys.platform.startswith("win"):
        flags = 0
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            flags |= subprocess.CREATE_NEW_PROCESS_GROUP
        return {"creationflags": flags}
    return {"start_new_session": True}


def _format_bytes(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return "{0:.1f}{1}".format(value, unit) if unit != "B" else "{0}B".format(int(value))
        value /= 1024
    return "{0}B".format(size)


def _validate_file_size(video_path, max_file_size=None):
    if not max_file_size:
        return
    size = os.path.getsize(video_path)
    if size > int(max_file_size):
        raise UploadError(
            "Exported file is too large: {0} > {1}".format(
                _format_bytes(size),
                _format_bytes(int(max_file_size)),
            )
        )


def start_local_bridge(video_path, prompt, target_url, timeout_seconds=10, max_file_size=None):
    video_path = os.path.abspath(video_path)
    if not os.path.exists(video_path):
        raise UploadError("Video file does not exist: {0}".format(video_path))

    video_path = standardize_mp4(video_path)
    _validate_file_size(video_path, max_file_size)

    return _start_python_bridge(video_path, prompt, target_url)


def upload_video(video_path, prompt, target_url, timeout_seconds=10):
    return start_local_bridge(video_path, prompt, target_url, timeout_seconds)
