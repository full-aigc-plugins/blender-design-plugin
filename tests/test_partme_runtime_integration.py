import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from types import ModuleType
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "runtime.lock.json"


class PartMeRuntimeIntegrationTests(unittest.TestCase):
    def test_same_version_loaded_from_another_directory_is_rejected(self):
        from scripts.partme_runtime import activate_runtime, RuntimeIntegrationError
        foreign = ModuleType('partme_blender_mcp')
        foreign.__version__ = json.loads(LOCK.read_text())['version']
        foreign.__file__ = '/tmp/unrelated/partme_blender_mcp/__init__.py'
        with mock.patch.dict(sys.modules, {'partme_blender_mcp': foreign}):
            with self.assertRaisesRegex(RuntimeIntegrationError, 'outside the pinned'):
                activate_runtime(ROOT)

    def test_foreign_cached_submodule_is_rejected(self):
        from scripts.partme_runtime import activate_runtime, RuntimeIntegrationError
        activate_runtime(ROOT)
        foreign = ModuleType('partme_blender_mcp.harness.foreign')
        foreign.__file__ = '/tmp/unrelated/foreign.py'
        with mock.patch.dict(sys.modules, {'partme_blender_mcp.harness.foreign': foreign}):
            with self.assertRaisesRegex(RuntimeIntegrationError, 'outside the pinned'):
                activate_runtime(ROOT)

    def test_lock_pins_release_artifacts_and_hashes(self):
        data = json.loads(LOCK.read_text(encoding="utf-8"))
        self.assertEqual(data["product"], "PartMe Blender MCP")
        self.assertEqual(data["version"], "0.6.1")
        self.assertEqual(data["repository"], "https://github.com/full-aigc-plugins/blender-mcp")
        for key in ("runtime", "addon"):
            artifact = data["artifacts"][key]
            path = ROOT / artifact["path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])
            self.assertIn("/releases/download/v0.6.1/", artifact["url"])

    def test_mcp_server_imports_the_pinned_runtime(self):
        from scripts.partme_runtime import activate_runtime

        runtime = activate_runtime(ROOT)
        self.assertEqual(runtime["version"], "0.6.1")
        module = importlib.import_module("partme_blender_mcp.harness.mcp_adapter")
        self.assertIn("partme-blender-mcp-runtime-0.6.1.zip", str(module.__file__))
        version = importlib.import_module("partme_blender_mcp.harness.version")
        self.assertEqual(version.MCP_PROTOCOL_VERSION, "2025-06-18")
        self.assertEqual(module.McpAdapter(plugin_root=ROOT).tools[0]["name"], "blender_getting_started")

        local = importlib.import_module("scripts.harness.mcp_adapter")
        self.assertNotIn("vendor/partme-blender-mcp", str(local.__file__))

    def test_connector_package_is_the_upstream_release_artifact(self):
        from scripts.package_connector import package_connector

        upstream = ROOT / "vendor/partme-blender-mcp-addon-0.6.1.zip"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "connector.zip"
            package_connector(target)
            self.assertEqual(target.read_bytes(), upstream.read_bytes())

    def test_connector_package_cli_uses_the_upstream_release_artifact(self):
        upstream = ROOT / "vendor/partme-blender-mcp-addon-0.6.1.zip"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "connector.zip"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/package_connector.py"), str(target)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), upstream.read_bytes())

    def test_runtime_loader_rejects_symlinked_vendor_artifact(self):
        from scripts.partme_runtime import RuntimeIntegrationError, locked_artifact

        with tempfile.TemporaryDirectory() as directory:
            plugin_root = Path(directory)
            (plugin_root / "vendor").mkdir()
            (plugin_root / "runtime.lock.json").write_bytes(LOCK.read_bytes())
            artifact = json.loads(LOCK.read_text(encoding="utf-8"))["artifacts"]["runtime"]
            source = plugin_root / "vendor/source.zip"
            source.write_bytes((ROOT / artifact["path"]).read_bytes())
            (plugin_root / artifact["path"]).symlink_to(source)
            with self.assertRaises(RuntimeIntegrationError):
                locked_artifact(plugin_root, "runtime")


if __name__ == "__main__":
    unittest.main()
