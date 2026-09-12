import json
import socket
import threading
import unittest

from scripts.harness.transport import Endpoint, JsonLineServer, choose_endpoint, send_request


class TestEndpointSelection(unittest.TestCase):
    def test_macos_prefers_unix_socket(self):
        endpoint = choose_endpoint("darwin", session_id="s1", runtime_dir="/tmp/runtime")
        self.assertEqual(endpoint.kind, "unix")
        self.assertTrue(endpoint.address.endswith("codex-blender-s1.sock"))

    def test_windows_prefers_named_pipe(self):
        endpoint = choose_endpoint("win32", session_id="s1", runtime_dir="ignored")
        self.assertEqual(endpoint.kind, "pipe")
        self.assertEqual(endpoint.address, r"\\.\pipe\codex-blender-s1")


class TestJsonLineServer(unittest.TestCase):
    def setUp(self):
        self.server = JsonLineServer(
            Endpoint("tcp", ("127.0.0.1", 0)),
            token="secret",
            handle=lambda payload: {"echo": payload["value"]},
            max_request_bytes=256,
        )
        self.server.start()

    def tearDown(self):
        self.server.close()

    def test_authenticated_request_round_trip(self):
        response = send_request(self.server.endpoint, "secret", {"value": 42})
        self.assertEqual(response, {"echo": 42})

    def test_wrong_token_is_rejected(self):
        response = send_request(self.server.endpoint, "wrong", {"value": 42})
        self.assertEqual(response["error"]["code"], "UNAUTHORIZED")

    def test_oversized_request_is_rejected(self):
        response = send_request(self.server.endpoint, "secret", {"value": "x" * 300})
        self.assertEqual(response["error"]["code"], "REQUEST_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
