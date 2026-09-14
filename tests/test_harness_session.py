import time
import unittest
from pathlib import Path

from scripts.harness.authorization import AuthorizationManager
from scripts.harness.execution_policy import ExecutionPolicy
from scripts.harness.errors import HarnessError
from scripts.harness.session import HarnessSession


def request(**overrides):
    payload = {
        "protocolVersion": "codex-blender/v1",
        "sessionId": "session-1",
        "requestId": "request-1",
        "transactionId": "tx-1",
        "command": "scene.inspect",
        "arguments": {},
    }
    payload.update(overrides)
    return payload


class TestAuthorizationManager(unittest.TestCase):
    def test_claim_is_bound_to_action_and_request(self):
        manager = AuthorizationManager(secret=b"s" * 32, now=lambda: 100)
        claim = manager.issue("request-1", "object.delete", ttl_seconds=30)
        self.assertTrue(manager.verify(claim, "request-1", "object.delete"))
        self.assertFalse(manager.verify(claim, "request-2", "object.delete"))
        self.assertFalse(manager.verify(claim, "request-1", "scene.save"))

    def test_expired_claim_is_rejected(self):
        clock = [100]
        manager = AuthorizationManager(secret=b"s" * 32, now=lambda: clock[0])
        claim = manager.issue("request-1", "object.delete", ttl_seconds=2)
        clock[0] = 103
        self.assertFalse(manager.verify(claim, "request-1", "object.delete"))


class TestHarnessSession(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def dispatch(command, arguments):
            self.calls.append((command, arguments))
            return {"changedObjects": [arguments.get("name", "")], "result": {"ok": True}}

        self.session = HarnessSession("session-1", dispatch=dispatch)

    def test_rejects_wrong_protocol(self):
        response = self.session.handle(request(protocolVersion="wrong"))
        self.assertEqual(response["status"], "failed")
        self.assertEqual(response["error"]["code"], "UNSUPPORTED_PROTOCOL")

    def test_rejects_wrong_session(self):
        response = self.session.handle(request(sessionId="other"))
        self.assertEqual(response["error"]["code"], "SESSION_MISMATCH")

    def test_duplicate_request_replays_without_dispatch(self):
        first = self.session.handle(request())
        second = self.session.handle(request())
        self.assertEqual(first, second)
        self.assertEqual(len(self.calls), 1)

    def test_mutation_requires_matching_revision(self):
        response = self.session.handle(
            request(command="object.create_mesh", expectedSceneRevision=9)
        )
        self.assertEqual(response["error"]["code"], "STALE_SCENE_REVISION")
        self.assertEqual(self.calls, [])

    def test_successful_mutation_increments_revision(self):
        response = self.session.handle(
            request(command="object.create_mesh", expectedSceneRevision=0, arguments={"name": "Body"})
        )
        self.assertEqual(response["status"], "succeeded")
        self.assertEqual(response["sceneRevision"], 1)
        self.assertEqual(response["changedObjects"], ["Body"])

    def test_gated_command_requires_authorization(self):
        response = self.session.handle(
            request(command="object.delete", expectedSceneRevision=0)
        )
        self.assertEqual(response["error"]["code"], "AUTHORIZATION_REQUIRED")

    def test_audit_log_redacts_authorization(self):
        manager = self.session.authorization
        claim = manager.issue("request-1", "object.delete", ttl_seconds=30)
        self.session.handle(
            request(command="object.delete", expectedSceneRevision=0, authorization=claim)
        )
        audit = self.session.audit_entries()
        self.assertEqual(audit[0]["authorization"], "[REDACTED]")
        self.assertNotIn(claim, str(audit))

    def test_confirmed_authorization_command_issues_action_bound_claim(self):
        response = self.session.handle(request(
            command="session.authorize",
            arguments={"action": "object.delete", "requestId": "delete-1", "userConfirmed": True},
        ))
        self.assertEqual(response["status"], "succeeded")
        claim = response["result"]["authorization"]
        self.assertTrue(self.session.authorization.verify(claim, "delete-1", "object.delete"))

    def test_authorization_command_rejects_missing_confirmation(self):
        response = self.session.handle(request(
            command="session.authorize",
            arguments={"action": "object.delete", "requestId": "delete-1"},
        ))
        self.assertEqual(response["error"]["code"], "USER_CONFIRMATION_REQUIRED")

    def test_auto_policy_is_recorded_without_bypassing_authorization(self):
        policy = ExecutionPolicy.auto_with_budget(str(Path.cwd()/'.test-out'), True, "3.20")
        session = HarnessSession("session-1", dispatch=lambda *_: {}, execution_policy=policy)
        response = session.handle(request(command="object.delete", expectedSceneRevision=0))
        self.assertEqual(response["error"]["code"], "AUTHORIZATION_REQUIRED")
        self.assertEqual(session.audit_entries()[0]["executionPolicy"]["mode"], "auto_with_budget")


if __name__ == "__main__":
    unittest.main()
