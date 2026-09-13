import unittest
import tempfile
from pathlib import Path

from scripts.harness.runtime import build_registry, create_session
from tests.test_design_commands import FakeBpy


class TestHarnessRuntime(unittest.TestCase):
    def test_registry_exposes_core_design_commands(self):
        registry = build_registry(FakeBpy())
        names = {entry["command"] for entry in registry.capabilities()}
        self.assertTrue({
            "scene.inspect", "object.create_mesh", "object.transform", "object.delete",
            "material.create_pbr", "material.assign", "camera.create", "light.create",
            "animation.set_frame_range", "animation.insert_keyframe", "preview.capture",
        }.issubset(names))
        response = registry.dispatch("session.capabilities", {})
        advertised = {item["command"] for item in response["result"]["commands"]}
        self.assertIn("object.create_mesh", advertised)

    def test_session_dispatches_real_registry_command(self):
        bpy = FakeBpy()
        session = create_session(bpy, "session-1")
        response = session.handle({
            "protocolVersion": "codex-blender/v1",
            "sessionId": "session-1",
            "requestId": "request-1",
            "transactionId": "tx-1",
            "command": "object.create_mesh",
            "arguments": {"primitive": "cube", "name": "Body"},
            "expectedSceneRevision": 0,
        })
        self.assertEqual(response["status"], "succeeded")
        self.assertIn("Body", bpy.data.objects)

    def test_command_arguments_are_closed(self):
        bpy = FakeBpy()
        session = create_session(bpy, "session-1")
        response = session.handle({
            "protocolVersion": "codex-blender/v1", "sessionId": "session-1",
            "requestId": "request-1", "transactionId": "tx-1",
            "command": "object.create_mesh",
            "arguments": {"primitive": "cube", "name": "Body", "shell": "unsafe"},
            "expectedSceneRevision": 0,
        })
        self.assertEqual(response["error"]["code"], "INVALID_ARGUMENT")
        self.assertNotIn("Body", bpy.data.objects)

    def test_export_command_is_gated_and_returns_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            bpy = FakeBpy()
            # Add the minimal exporter surface used by this integration test.
            bpy.ops.wm = type("Wm", (), {"save_as_mainfile": lambda _self, **kwargs: Path(kwargs["filepath"]).write_bytes(b"blend")})()
            session = create_session(bpy, "session-1", approved_output_root=Path(directory))
            payload = {
                "protocolVersion": "codex-blender/v1",
                "sessionId": "session-1",
                "requestId": "export-1",
                "transactionId": "tx-1",
                "command": "export.file",
                "arguments": {"path": str(Path(directory) / "design.blend"), "snapshotId": "snap-1"},
                "expectedSceneRevision": 0,
            }
            denied = session.handle(payload)
            self.assertEqual(denied["error"]["code"], "AUTHORIZATION_REQUIRED")
            payload["authorization"] = session.authorization.issue("export-1", "export.file")
            payload["requestId"] = "export-2"
            payload["authorization"] = session.authorization.issue("export-2", "export.file")
            accepted = session.handle(payload)
            self.assertEqual(accepted["status"], "succeeded")
            self.assertEqual(accepted["result"]["artifact"]["format"], "blend")


if __name__ == "__main__":
    unittest.main()
