import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import mcp_bootstrap

ROOT = Path(__file__).resolve().parents[1]


class McpBootstrapTests(unittest.TestCase):
    def test_load_lock_verifies_the_published_runtime_archive(self):
        lock, archive, digest = mcp_bootstrap._load_lock(ROOT)

        self.assertEqual(lock["version"], "0.7.0-rc.2")
        self.assertEqual(archive.name, "partme-blender-mcp-runtime-0.7.0-rc.2.zip")
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), digest)

    def test_explicit_cache_is_version_scoped(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"PARTME_BLENDER_MCP_CACHE": directory}, clear=False,
        ):
            self.assertEqual(mcp_bootstrap._cache_root("0.5.3"), Path(directory) / "runtime/0.5.3")

    def test_compatible_python_honors_explicit_supported_interpreter(self):
        with mock.patch.dict(
            os.environ, {"PARTME_BLENDER_MCP_PYTHON": "/opt/partme/python"}, clear=False,
        ), mock.patch.object(mcp_bootstrap, "_python_version", return_value=(3, 13)) as probe:
            self.assertEqual(mcp_bootstrap._compatible_python(), ["/opt/partme/python"])
            probe.assert_called_once_with(["/opt/partme/python"])

    def test_symlinked_runtime_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin_root = Path(directory)
            (plugin_root / "vendor").mkdir()
            lock = json.loads((ROOT / "runtime.lock.json").read_text(encoding="utf-8"))
            (plugin_root / "runtime.lock.json").write_text(json.dumps(lock), encoding="utf-8")
            artifact = lock["artifacts"]["runtime"]
            target = plugin_root / "runtime.zip"
            target.write_bytes((ROOT / artifact["path"]).read_bytes())
            (plugin_root / artifact["path"]).symlink_to(target)

            with self.assertRaisesRegex(mcp_bootstrap.BootstrapError, "unsafe"):
                mcp_bootstrap._load_lock(plugin_root)

    def test_acquire_lock_recovers_dead_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "install.lock"
            lock_path.write_text("99999999", encoding="ascii")
            with mock.patch.object(mcp_bootstrap.os, "kill", side_effect=ProcessLookupError):
                descriptor = mcp_bootstrap._acquire_lock(lock_path)
            try:
                self.assertEqual(lock_path.read_text(encoding="ascii"), str(os.getpid()))
            finally:
                os.close(descriptor)


if __name__ == "__main__":
    unittest.main()
