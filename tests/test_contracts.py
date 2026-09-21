import json
import unittest
from pathlib import Path

from scripts.validate_document import validate_document


ROOT = Path(__file__).resolve().parents[1]
VALID_ARTIFACT = {
    "protocolVersion": "codex-blender/v1",
    "producer": {"name": "codex-blender", "version": "0.3.0"},
    "sessionId": "s1",
    "sceneRevision": 7,
    "snapshotId": "snapshot-7",
    "path": "/tmp/design.glb",
    "sha256": "a" * 64,
    "format": "glb",
    "bytes": 100,
    "parameters": {},
    "validation": {"status": "passed", "checks": ["exists", "sha256"]},
    "restoration": {"status": "confirmed"},
    "warnings": [],
}


class TestManifest(unittest.TestCase):
    def test_identity_and_skill_path(self):
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "blender-design")
        self.assertRegex(manifest["version"], r"^0\.13\.0(?:\+codex\.[0-9A-Za-z.-]+)?$")
        self.assertEqual(manifest["skills"], "./skills/")


class TestArtifactReceipt(unittest.TestCase):
    def test_valid_receipt(self):
        self.assertEqual(validate_document("artifact_receipt", VALID_ARTIFACT), [])

    def test_schema_is_closed(self):
        self.assertTrue(validate_document("artifact_receipt", {**VALID_ARTIFACT, "unknown": 1}))

    def test_hash_and_format_are_enforced(self):
        self.assertTrue(validate_document("artifact_receipt", {**VALID_ARTIFACT, "sha256": "bad"}))
        self.assertTrue(validate_document("artifact_receipt", {**VALID_ARTIFACT, "format": "exe"}))

    def test_restoration_status_is_enforced(self):
        payload = {**VALID_ARTIFACT, "restoration": {"status": "partial"}}
        self.assertTrue(validate_document("artifact_receipt", payload))


if __name__ == "__main__":
    unittest.main()
