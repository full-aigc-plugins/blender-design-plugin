"""Tests for the first-run blender_auto_setup engine (scripts/auto_setup.py)."""

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from scripts import auto_setup

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _fake_blender(script_root: Path, enabled: bool = True) -> Path:
    """A stub blender binary answering the CLI queries auto_setup relies on."""
    body = f"""#!/bin/sh
for last in "$@"; do :; done
case "$last" in
  *PARTME_SCRIPTS*)
    echo "PARTME_SCRIPTS={script_root}"
    ;;
  *addon_utils*)
    echo "PARTME_ENABLED={'True' if enabled else 'False'}"
    ;;
esac
exit 0
"""
    path = script_root.parent / "fake-blender.sh"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


def _make_addon_zip(target: Path) -> Path:
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("partme_blender_mcp/__init__.py", "# addon\n")
        archive.writestr("partme_blender_mcp/panel.py", "# panel\n")
    return target


class DiscoverBlenderTests(unittest.TestCase):
    def test_env_override_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "blender-bin"
            fake.write_text("#!/bin/sh\nexit 0\n")
            fake.chmod(0o755)
            with mock.patch.dict(auto_setup.__dict__ and __import__("os").environ, {"PARTME_BLENDER_BIN": str(fake)}):
                self.assertEqual(auto_setup.discover_blender(), fake)

    def test_missing_blender_reports_download_hint(self):
        with mock.patch.object(auto_setup, "_candidate_blender_paths", return_value=[]):
            self.assertIsNone(auto_setup.discover_blender())
            result = auto_setup.run_auto_setup(PLUGIN_ROOT)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "discover")
        self.assertIn("blender.org", result["manualHint"])


class ResolveScriptsRootTests(unittest.TestCase):
    def test_cli_query_creates_addons_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            script_root = Path(tmp) / "4.5" / "scripts"
            blender_bin = _fake_blender(script_root)
            addons = auto_setup.resolve_scripts_root(blender_bin)
            self.assertEqual(addons, script_root / "addons")

    def test_fallback_scan_when_cli_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Blender Foundation" / "Blender"
            (base / "4.2" / "scripts").mkdir(parents=True)
            (base / "4.5" / "scripts").mkdir(parents=True)
            with mock.patch.object(
                auto_setup, "_standard_script_roots",
                return_value=[base / "4.5" / "scripts", base / "4.2" / "scripts"],
            ), mock.patch.object(auto_setup, "scripts_root_via_cli", return_value=None):
                addons = auto_setup.resolve_scripts_root(None)
            self.assertEqual(addons, base / "4.5" / "scripts" / "addons")


class ResolveAddonZipTests(unittest.TestCase):
    def test_falls_back_to_bundled_when_offline(self):
        with mock.patch.object(auto_setup, "_release_payload", return_value=None):
            path, source = auto_setup.resolve_addon_zip(PLUGIN_ROOT)
        self.assertEqual(path, auto_setup.bundled_addon_zip(PLUGIN_ROOT))
        self.assertTrue(source.startswith("bundled"))

    def test_downloads_newer_release(self):
        release = {
            "tag_name": "v9.9.9",
            "assets": [
                {"name": "partme-blender-mcp-addon-9.9.9.zip", "browser_download_url": "https://example/addon.zip"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = _make_addon_zip(Path(tmp) / "addon.zip")
            data = zip_path.read_bytes()

            def fake_urlopen(req, timeout=0):
                class Response:
                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        return False

                    def read(self):
                        return data

                return Response()

            with mock.patch.object(auto_setup, "_release_payload", return_value=release), \
                 mock.patch.object(auto_setup._urlrequest, "urlopen", side_effect=fake_urlopen):
                path, source = auto_setup.resolve_addon_zip(PLUGIN_ROOT)
            self.assertTrue(source.startswith("github-release v9.9.9"))
            with zipfile.ZipFile(path) as archive:
                self.assertIn("partme_blender_mcp/__init__.py", archive.namelist())


class InstallAddonTests(unittest.TestCase):
    def test_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = _make_addon_zip(Path(tmp) / "addon.zip")
            addons = Path(tmp) / "addons"
            first = auto_setup.install_addon(addons, zip_path)
            (first / "panel.py").write_text("# replaced\n")
            second = auto_setup.install_addon(addons, zip_path)
            self.assertEqual(first, second)
            self.assertEqual((second / "panel.py").read_text(), "# panel\n")


class EnableAndLaunchTests(unittest.TestCase):
    def test_enable_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            script_root = Path(tmp) / "4.5" / "scripts"
            blender_bin = _fake_blender(script_root, enabled=True)
            self.assertTrue(auto_setup.enable_addon_persistently(blender_bin))

    def test_autostart_expression_targets_connector_operator(self):
        expression = auto_setup.autostart_expression(Path("/tmp/out"))
        self.assertIn("partme_blender_output_root", expression)
        self.assertIn("partme_blender.start_connector", expression)
        self.assertIn("/tmp/out", expression)


class RunAutoSetupTests(unittest.TestCase):
    def test_running_blender_blocks_enable_with_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            script_root = Path(tmp) / "4.5" / "scripts"
            blender_bin = _fake_blender(script_root)
            with mock.patch.object(auto_setup, "discover_blender", return_value=blender_bin), \
                 mock.patch.object(auto_setup, "blender_running", return_value=True), \
                 mock.patch.dict(__import__("os").environ, {"PARTME_BLENDER_OUTPUT_ROOT": str(Path(tmp) / "out")}):
                result = auto_setup.run_auto_setup(PLUGIN_ROOT)
            self.assertFalse(result["ok"])
            self.assertEqual(result["stage"], "enable")
            self.assertIn("完全退出 Blender", result["manualHint"])
            installed = [s for s in result["steps"] if s["step"] == "install"]
            self.assertTrue(installed and installed[0]["ok"])

    def test_happy_path_installs_enables_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            script_root = Path(tmp) / "4.5" / "scripts"
            blender_bin = _fake_blender(script_root)
            launched = mock.Mock(pid=4321)
            with mock.patch.object(auto_setup, "discover_blender", return_value=blender_bin), \
                 mock.patch.object(auto_setup, "blender_running", return_value=False), \
                 mock.patch.object(auto_setup, "launch_connected", return_value=launched) as launch, \
                 mock.patch.dict(__import__("os").environ, {"PARTME_BLENDER_OUTPUT_ROOT": str(Path(tmp) / "out")}):
                result = auto_setup.run_auto_setup(PLUGIN_ROOT)
            self.assertTrue(result["ok"])
            self.assertTrue(result["stage"] == "launch")
            self.assertEqual(result["launchedPid"], 4321)
            launch.assert_called_once()
            self.assertEqual(launch.call_args[0][1], Path(tmp) / "out")


if __name__ == "__main__":
    unittest.main()
