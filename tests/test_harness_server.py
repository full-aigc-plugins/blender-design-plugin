import json
import tempfile
import unittest
from pathlib import Path

from scripts.harness.server import start_harness
from scripts.harness.transport import Endpoint, send_request
from tests.test_design_commands import FakeBpy


class Timers:
    def __init__(self):
        self.callback = None

    def register(self, callback, first_interval=0.0, persistent=False):
        self.callback = callback

    def unregister(self, callback):
        if self.callback is callback:
            self.callback = None


class TestHarnessServer(unittest.TestCase):
    def test_descriptor_is_private_and_server_dispatches_on_timer(self):
        with tempfile.TemporaryDirectory() as directory:
            bpy = FakeBpy()
            bpy.app = type("App", (), {"timers": Timers()})()
            runtime = start_harness(
                bpy,
                session_id="session-1",
                runtime_dir=Path(directory),
                endpoint=Endpoint("tcp", ("127.0.0.1", 0)),
            )
            try:
                descriptor = Path(directory) / "session-1.json"
                payload = json.loads(descriptor.read_text())
                self.assertEqual(descriptor.stat().st_mode & 0o777, 0o600)
                request = {
                    "protocolVersion": "codex-blender/v1",
                    "sessionId": "session-1",
                    "requestId": "request-1",
                    "transactionId": "tx-1",
                    "command": "scene.inspect",
                    "arguments": {},
                }
                import threading
                result = []
                thread = threading.Thread(target=lambda: result.append(send_request(runtime.endpoint, payload["token"], request, timeout=2)))
                thread.start()
                while thread.is_alive():
                    bpy.app.timers.callback()
                thread.join()
                self.assertEqual(result[0]["status"], "succeeded")
            finally:
                runtime.close()
            self.assertFalse(descriptor.exists())


if __name__ == "__main__":
    unittest.main()
