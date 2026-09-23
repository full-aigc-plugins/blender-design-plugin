"""Tests for the asset.fetch_url closed command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest
from pathlib import Path
from unittest import mock

from scripts.harness.commands.asset import AssetCommands
from scripts.harness.errors import HarnessError
from scripts.harness.path_policy import PathPolicy


class FakeBpy:
    class data:
        objects = []
    class ops:
        class file:
            pack_all = staticmethod(lambda: {"FINISHED"})
            make_paths_relative = staticmethod(lambda: {"FINISHED"})
    class context:
        class scene:
            class collection:
                objects = None
                children = None


def make_commands(tmp_path):
    policy = PathPolicy([tmp_path])
    return AssetCommands(FakeBpy, asset_policy=policy), tmp_path


class FakeResponse:
    def __init__(self, body=b"asset-bytes", headers=None):
        self._body = body
        self.headers = headers or {"Content-Length": str(len(body))}
    def read(self, size=-1):
        chunk, self._body = self._body[:size if size > 0 else None], self._body[size if size > 0 else None:]
        return chunk
    def __enter__(self):
        return self
    def __exit__(self, *_a):
        return False


class FetchUrlTests(unittest.TestCase):
    def test_download_writes_into_approved_root(self):
        cmds, _tmp = make_commands(tmp_root := __import__("tempfile").mkdtemp())
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(b"asset-bytes")):
            result = cmds.fetch_url({"url": "https://dl.polyhaven.org/file/admin/assets/hdris/sunset/1k/sunset_1k.hdr"})
        target = Path(result["result"]["path"])
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_bytes(), b"asset-bytes")
        self.assertFalse(result["result"]["cached"])
        self.assertTrue(str(target).startswith(str(Path(tmp_root).resolve())))
        self.assertEqual(target.suffix, ".hdr")

    def test_cached_download_is_idempotent(self):
        cmds, _tmp = make_commands(__import__("tempfile").mkdtemp())
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(b"abc")):
            first = cmds.fetch_url({"url": "https://dl.polyhaven.org/x/pbr/wood_1k.png"})
        urlopen = mock.Mock(side_effect=AssertionError("must not re-download"))
        with mock.patch("urllib.request.urlopen", urlopen):
            second = cmds.fetch_url({"url": "https://dl.polyhaven.org/x/pbr/wood_1k.png"})
        self.assertTrue(second["result"]["cached"])
        self.assertEqual(second["result"]["path"], first["result"]["path"])

    def test_non_whitelisted_host_is_rejected(self):
        cmds, _ = make_commands(__import__("tempfile").mkdtemp())
        with self.assertRaises(HarnessError) as caught:
            cmds.fetch_url({"url": "https://evil.example.com/x/model.glb"})
        self.assertIn("not approved", str(caught.exception))

    def test_non_https_is_rejected(self):
        cmds, _ = make_commands(__import__("tempfile").mkdtemp())
        with self.assertRaises(HarnessError):
            cmds.fetch_url({"url": "http://dl.polyhaven.org/x/a.hdr"})

    def test_disallowed_suffix_is_rejected(self):
        cmds, _ = make_commands(__import__("tempfile").mkdtemp())
        with self.assertRaises(HarnessError):
            cmds.fetch_url({"url": "https://dl.polyhaven.org/x/payload.exe"})





class DefaultAssetRootTests(unittest.TestCase):
    def test_default_root_fallback(self):
        from scripts.harness.server import default_asset_roots
        self.assertEqual(
            default_asset_roots(()),
            (Path.home() / "Documents" / "partme-blender" / "assets",),
        )

    def test_explicit_roots_win_over_default(self):
        from scripts.harness.server import default_asset_roots
        self.assertEqual(default_asset_roots(("/custom/root",)), ("/custom/root",))

if __name__ == "__main__":
    unittest.main()
