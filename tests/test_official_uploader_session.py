"""Session audit privacy tests for official uploader commands."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.harness.runtime import create_session
from tests.test_official_uploader import _bpy


class OfficialUploaderSessionTests(unittest.TestCase):
    def test_audit_projection_never_persists_prompt_paths_url_or_token(self):
        sys.modules["jimeng_blender_uploader"] = SimpleNamespace(bl_info={"version": (1, 0, 0), "blender": (5, 2, 0)})
        self.addCleanup(sys.modules.pop, "jimeng_blender_uploader", None)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "private-input.mp4"
            video.write_bytes(b"video")
            session = create_session(_bpy(current_link=True), "audit", runtime_mode="connector", approved_output_root=root, approved_asset_roots=(root,))
            response = session.handle({
                "protocolVersion": "codex-blender/v1", "sessionId": "audit",
                "requestId": "req-upload", "transactionId": "tx-upload",
                "expectedSceneRevision": 0,
                "command": "official_uploader.link_existing",
                "arguments": {"videoPath": str(video), "prompt": "private prompt"},
            })
            self.assertEqual(response["status"], "failed")
            self.assertEqual(response["error"]["code"], "AUTHORIZATION_REQUIRED")
            audit = session.audit_entries()[0]
            rendered = str(audit)
            self.assertNotIn("private prompt", rendered)
            self.assertNotIn(str(video), rendered)
            self.assertNotIn("thirdparty_id", rendered)
            self.assertNotIn("secret", rendered)
            self.assertEqual(audit["command"], "official_uploader.link_existing")
            self.assertEqual(audit["requestId"], "req-upload")


if __name__ == "__main__":
    unittest.main()
