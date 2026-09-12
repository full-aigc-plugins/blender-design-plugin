import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_document import validate_document


class TestHarnessIdentity(unittest.TestCase):
    def test_manifest_describes_blender_design_not_dreamina(self):
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        searchable = json.dumps(manifest, ensure_ascii=False).lower()
        self.assertIn("design", searchable)
        self.assertIn("export", searchable)
        self.assertNotIn("jimeng", searchable)
        self.assertNotIn("dreamina", searchable)


class TestHarnessCommandSchema(unittest.TestCase):
    def test_valid_command(self):
        payload = {
            "protocolVersion": "codex-blender/v1",
            "sessionId": "session-1",
            "requestId": "request-1",
            "transactionId": "tx-1",
            "command": "object.create_mesh",
            "arguments": {"primitive": "cube", "name": "Body"},
            "expectedSceneRevision": 0,
        }
        self.assertEqual(validate_document("command", payload), [])

    def test_command_is_closed(self):
        payload = {
            "protocolVersion": "codex-blender/v1",
            "sessionId": "session-1",
            "requestId": "request-1",
            "transactionId": "tx-1",
            "command": "scene.inspect",
            "arguments": {},
            "unexpected": True,
        }
        self.assertTrue(validate_document("command", payload))


class TestHarnessResponseSchema(unittest.TestCase):
    def test_valid_response(self):
        payload = {
            "protocolVersion": "codex-blender/v1",
            "requestId": "request-1",
            "status": "succeeded",
            "sceneRevision": 1,
            "changedObjects": ["Body"],
            "warnings": [],
            "snapshotId": "snapshot-1",
        }
        self.assertEqual(validate_document("response", payload), [])


class TestMilestoneReceiptSchema(unittest.TestCase):
    def test_valid_milestone(self):
        view = {
            "name": "camera",
            "path": "/tmp/camera.png",
            "sha256": "a" * 64,
        }
        payload = {
            "protocolVersion": "codex-blender/v1",
            "milestone": "modeling",
            "sceneRevision": 3,
            "snapshotId": "snapshot-3",
            "views": [view],
            "sceneSummary": {"objects": 1, "materials": 0, "lights": 0, "cameras": 1},
            "warnings": [],
        }
        self.assertEqual(validate_document("milestone_receipt", payload), [])


if __name__ == "__main__":
    unittest.main()
