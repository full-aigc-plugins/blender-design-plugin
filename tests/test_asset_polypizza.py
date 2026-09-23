"""Tests for the Poly Pizza closed commands (asset.polypizza_search / asset.polypizza_download)."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys_path = str(Path(__file__).resolve().parents[1])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from scripts.harness.commands.asset import AssetCommands
from scripts.harness.errors import HarnessError
from scripts.harness.path_policy import PathPolicy

KEY_ENV = {"POLYPIZZA_API_KEY": "test-key"}

SEARCH_RESPONSE = {
    "total": 1,
    "results": [{
        "ID": "abc123", "Title": "Low Chair", "Creator": {"Username": "remster"},
        "Licence": 0, "Tri Count": 420, "Animated": False, "Category": 3, "Tags": ["furniture"],
    }],
}

MODEL_RESPONSE = {
    "ID": "abc123", "Title": "Low Chair", "Creator": {"Username": "remster"},
    "Licence": 0, "Download": "https://static.poly.pizza/files/abc123.glb",
}

CDN_GLB = b"glTF-model-bytes"


class FakeBpy:
    class data:
        objects = []  # noqa: RUF012
    class ops:
        class file:
            pack_all = staticmethod(lambda: {"FINISHED"})
            make_paths_relative = staticmethod(lambda: {"FINISHED"})


class FakeResponse:
    def __init__(self, body=b"", headers=None):
        self._body = body
        self.headers = headers or {}
    def read(self, size=-1):
        keep = size if size and size > 0 else len(self._body)
        chunk, self._body = self._body[:keep], self._body[keep:]
        return chunk
    def __enter__(self):
        return self
    def __exit__(self, *_a):
        return False


class PolypizzaTestBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.tmp_root = Path(tmp).resolve()
        self.policy = PathPolicy([tmp])
        self.cmds = AssetCommands(FakeBpy, asset_policy=self.policy)
        self.env = mock.patch.dict(os.environ, KEY_ENV)

    def responses(self, *outcomes):
        return mock.patch("urllib.request.urlopen", side_effect=list(outcomes))


class PolypizzaSearchTests(PolypizzaTestBase):
    def run_search(self, arguments):
        with self.env, mock.patch(
            "urllib.request.urlopen",
            (lambda request, timeout=30: FakeResponse(
                200, json.dumps(SEARCH_RESPONSE).encode("utf-8"),
                {"Content-Type": "application/json"},
            )),
        ):
            return self.cmds.polypizza_search(arguments)

    def run_search_capture(self, arguments, capture):
        def fake_urlopen(request, timeout=30):
            capture.update(full_url=request.full_url, headers=dict(request.header_items()))
            return FakeResponse(json.dumps(SEARCH_RESPONSE).encode("utf-8"),
                                {"Content-Type": "application/json"})
        with self.env, mock.patch("urllib.request.urlopen", fake_urlopen):
            return self.cmds.polypizza_search(arguments)

    def test_search_requires_api_key(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(HarnessError) as caught:
            self.cmds.polypizza_search({"query": "chair"})
        self.assertIn("POLYPIZZA_API_KEY", str(caught.exception))

    def test_search_maps_fields_and_licence(self):
        capture = {}
        result = self.run_search_capture({"query": "chair", "licence": "CC-BY", "limit": 5}, capture)
        self.assertIn("/search/chair", capture["full_url"])
        self.assertIn("Limit=5", capture["full_url"])
        self.assertIn("License=0", capture["full_url"])  # CC-BY -> id 0
        model = result["result"]["models"][0]
        self.assertEqual(model["id"], "abc123")
        self.assertEqual(model["creator"], "remster")
        self.assertEqual(model["licence"], "CC-BY")

    def test_invalid_licence_is_rejected(self):
        with self.assertRaises(HarnessError):
            self.run_search({"query": "chair", "licence": "WTFPL"})


class PolypizzaDownloadTests(PolypizzaTestBase):
    def run_download(self, arguments, extra_outcomes=()):
        with self.env, mock.patch(
            "urllib.request.urlopen",
            side_effect=[
                FakeResponse(json.dumps(MODEL_RESPONSE).encode("utf-8"),
                             {"Content-Type": "application/json"}),
                FakeResponse(CDN_GLB, {"Content-Type": "model/gltf-binary"}),
                *extra_outcomes,
            ],
        ):
            return self.cmds.polypizza_download(arguments)

    def test_download_writes_model_and_license_sidecar(self):
        result = self.run_download({"modelId": "abc123"})
        target = Path(result["result"]["path"])
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_bytes(), CDN_GLB)
        self.assertTrue(str(target).startswith(str(self.tmp_root)))
        self.assertEqual(result["result"]["licence"], "CC-BY")
        self.assertIn("remster", result["result"]["attribution"])
        sidecar = Path(result["result"]["sidecar"])
        self.assertTrue(sidecar.is_file())
        self.assertIn("CC-BY", sidecar.read_text(encoding="utf-8"))

    def test_download_rejects_oversize(self):
        with mock.patch.object(AssetCommands, "POLYPIZZA_MAX_BYTES", 10), self.assertRaises(HarnessError):
            self.run_download({"modelId": "abc123"})


if __name__ == "__main__":
    unittest.main()
