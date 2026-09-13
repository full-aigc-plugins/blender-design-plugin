import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.harness.errors import HarnessError
from scripts.harness.transaction import TransactionManager
from scripts.harness.session import HarnessSession


class TestTransactionManager(unittest.TestCase):
    def setUp(self):
        self.state = {"objects": ["A"], "revision": 1}

    def capture(self):
        return deepcopy(self.state)

    def restore(self, snapshot):
        self.state.clear()
        self.state.update(deepcopy(snapshot))

    def test_failure_rolls_back_all_changes(self):
        manager = TransactionManager(capture=self.capture, restore=self.restore)
        manager.begin("tx-1", scene_revision=1)

        def fail():
            self.state["objects"].append("B")
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            manager.execute("tx-1", fail)
        self.assertEqual(self.state, {"objects": ["A"], "revision": 1})
        self.assertEqual(manager.status("tx-1")["restoration"], "confirmed")

    def test_commit_returns_revision_bound_snapshot(self):
        manager = TransactionManager(capture=self.capture, restore=self.restore)
        manager.begin("tx-1", scene_revision=1)
        self.state["objects"].append("B")
        receipt = manager.commit("tx-1", scene_revision=2)
        self.assertEqual(receipt["sceneRevision"], 2)
        self.assertTrue(receipt["snapshotId"].startswith("snapshot-"))
        self.assertEqual(manager.status("tx-1")["state"], "committed")

    def test_duplicate_active_transaction_is_rejected(self):
        manager = TransactionManager(capture=self.capture, restore=self.restore)
        manager.begin("tx-1", scene_revision=1)
        with self.assertRaises(HarnessError) as caught:
            manager.begin("tx-1", scene_revision=1)
        self.assertEqual(caught.exception.code, "TRANSACTION_EXISTS")

    def test_recovery_journal_contains_no_snapshot_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "recovery.json"
            manager = TransactionManager(capture=self.capture, restore=self.restore, journal_path=journal)
            manager.begin("tx-1", scene_revision=1)
            manager.commit("tx-1", scene_revision=2)
            payload = json.loads(journal.read_text())
            self.assertEqual(payload["transactions"][0]["transactionId"], "tx-1")
            self.assertNotIn("objects", journal.read_text())


class TestSessionTransactionIntegration(unittest.TestCase):
    def test_failed_second_mutation_rolls_back_first_and_revision(self):
        state = {"objects": []}
        manager = TransactionManager(capture=lambda: deepcopy(state), restore=lambda snapshot: state.update(deepcopy(snapshot)))

        def dispatch(command, arguments):
            if command == "object.create_mesh":
                state["objects"].append(arguments["name"])
                return {"changedObjects": [arguments["name"]]}
            raise ValueError("injected failure")

        session = HarnessSession("s1", dispatch=dispatch, transactions=manager)
        begin = session.handle({
            "protocolVersion": "codex-blender/v1", "sessionId": "s1", "requestId": "begin",
            "transactionId": "tx1", "command": "transaction.begin", "arguments": {},
        })
        self.assertEqual(begin["status"], "succeeded")
        first = session.handle({
            "protocolVersion": "codex-blender/v1", "sessionId": "s1", "requestId": "one",
            "transactionId": "tx1", "command": "object.create_mesh", "arguments": {"name": "A"},
            "expectedSceneRevision": 0,
        })
        self.assertEqual(first["sceneRevision"], 1)
        failed = session.handle({
            "protocolVersion": "codex-blender/v1", "sessionId": "s1", "requestId": "two",
            "transactionId": "tx1", "command": "object.transform", "arguments": {},
            "expectedSceneRevision": 1,
        })
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(session.scene_revision, 0)
        self.assertEqual(state["objects"], [])
        self.assertEqual(manager.status("tx1")["restoration"], "confirmed")

    def test_export_requires_committed_snapshot_at_current_revision(self):
        state = {"objects": []}
        manager = TransactionManager(capture=lambda: deepcopy(state), restore=lambda snapshot: state.update(deepcopy(snapshot)))
        session = HarnessSession("s1", dispatch=lambda command, args: {"result": {"artifact": args}}, transactions=manager)
        denied = session.handle({
            "protocolVersion": "codex-blender/v1", "sessionId": "s1", "requestId": "export-1",
            "transactionId": "tx1", "command": "export.file", "arguments": {"snapshotId": "unknown"},
            "authorization": session.authorization.issue("export-1", "export.file"),
        })
        self.assertEqual(denied["error"]["code"], "MILESTONE_NOT_APPROVED")

        session.handle({"protocolVersion": "codex-blender/v1", "sessionId": "s1", "requestId": "begin", "transactionId": "tx1", "command": "transaction.begin", "arguments": {}})
        committed = session.handle({"protocolVersion": "codex-blender/v1", "sessionId": "s1", "requestId": "commit", "transactionId": "tx1", "command": "transaction.commit", "arguments": {}})
        snapshot_id = committed["snapshotId"]
        accepted = session.handle({
            "protocolVersion": "codex-blender/v1", "sessionId": "s1", "requestId": "export-2",
            "transactionId": "tx1", "command": "export.file", "arguments": {"snapshotId": snapshot_id},
            "authorization": session.authorization.issue("export-2", "export.file"),
        })
        self.assertEqual(accepted["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
