"""Session revision, idempotency, authorization, and audit boundary."""

from __future__ import annotations

import copy
from collections import OrderedDict
from collections.abc import Callable

from .authorization import AuthorizationManager
from .execution_policy import ExecutionPolicy
from .errors import HarnessError
from .protocol import CommandRequest, PROTOCOL_VERSION


READ_ONLY_COMMANDS = {
    "session.capabilities", "session.status", "scene.inspect", "preview.capture", "export.file",
    "transaction.begin", "transaction.commit", "transaction.rollback", "session.authorize",
}
GATED_COMMANDS = {
    "object.delete",
    "scene.new",
    "scene.open",
    "scene.save",
    "scene.save_as",
    "export.final",
    "export.file",
    "advanced.execute_python",
    "session.close",
}


class HarnessSession:
    def __init__(
        self,
        session_id: str,
        *,
        dispatch: Callable[[str, dict], dict],
        authorization: AuthorizationManager | None = None,
        transactions=None,
        replay_limit: int = 512,
        execution_policy: ExecutionPolicy | None = None,
    ):
        self.session_id = session_id
        self.scene_revision = 0
        self.dispatch = dispatch
        self.authorization = authorization or AuthorizationManager()
        self.transactions = transactions
        self._replay_limit = replay_limit
        self._responses: OrderedDict[str, dict] = OrderedDict()
        self._audit: list[dict] = []
        self._approved_snapshots: dict[str, int] = {}
        self.execution_policy = execution_policy or ExecutionPolicy.interactive()

    def handle(self, payload: dict) -> dict:
        request_id = payload.get("requestId", "") if isinstance(payload, dict) else ""
        if request_id in self._responses:
            return copy.deepcopy(self._responses[request_id])
        try:
            request = CommandRequest.parse(payload)
            if request.session_id != self.session_id:
                raise HarnessError("SESSION_MISMATCH", "request session does not match active session")
            if request.command.startswith("transaction."):
                response = self._handle_transaction(request)
                self._remember(request_id, response)
                self._record_audit(payload, response)
                return copy.deepcopy(response)
            if request.command == "session.authorize":
                response = self._handle_authorize(request)
                self._remember(request_id, response)
                self._record_audit(payload, response)
                return copy.deepcopy(response)
            mutation = request.command not in READ_ONLY_COMMANDS
            if mutation and request.expected_scene_revision != self.scene_revision:
                raise HarnessError(
                    "STALE_SCENE_REVISION",
                    f"expected scene revision {self.scene_revision}",
                    retryable=True,
                )
            if request.command in GATED_COMMANDS and not self.authorization.verify(
                request.authorization, request.request_id, request.command
            ):
                raise HarnessError("AUTHORIZATION_REQUIRED", f"authorization required for {request.command}")
            if request.command == "export.file" and self.transactions is not None:
                snapshot_id = request.arguments.get("snapshotId")
                if self._approved_snapshots.get(snapshot_id) != self.scene_revision:
                    raise HarnessError(
                        "MILESTONE_NOT_APPROVED",
                        "export snapshot is not committed at the current scene revision",
                    )
            if mutation and self.transactions is not None:
                result = self.transactions.execute(
                    request.transaction_id,
                    lambda: self.dispatch(request.command, request.arguments),
                ) or {}
            else:
                result = self.dispatch(request.command, request.arguments) or {}
            if mutation:
                self.scene_revision += 1
            response = {
                "protocolVersion": PROTOCOL_VERSION,
                "requestId": request.request_id,
                "status": "succeeded",
                "sceneRevision": self.scene_revision,
                "changedObjects": list(result.get("changedObjects", [])),
                "warnings": list(result.get("warnings", [])),
            }
            if "snapshotId" in result:
                response["snapshotId"] = result["snapshotId"]
            if "result" in result:
                response["result"] = result["result"]
        except HarnessError as exc:
            self._sync_rolled_back_revision(payload)
            response = self._error_response(request_id, exc)
        except Exception as exc:
            self._sync_rolled_back_revision(payload)
            response = self._error_response(request_id, HarnessError("COMMAND_FAILED", str(exc)))
        self._remember(request_id, response)
        self._record_audit(payload, response)
        return copy.deepcopy(response)

    def _error_response(self, request_id: str, error: HarnessError) -> dict:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "requestId": request_id,
            "status": "failed",
            "sceneRevision": self.scene_revision,
            "changedObjects": [],
            "warnings": [],
            "error": {"code": error.code, "message": str(error), "retryable": error.retryable},
        }

    def _sync_rolled_back_revision(self, payload) -> None:
        if self.transactions is None or not isinstance(payload, dict):
            return
        try:
            transaction_status = self.transactions.status(payload.get("transactionId"))
            if transaction_status["state"] == "rolled_back":
                self.scene_revision = transaction_status["beginRevision"]
        except Exception:
            pass

    def _handle_transaction(self, request: CommandRequest) -> dict:
        if self.transactions is None:
            raise HarnessError("TRANSACTIONS_UNAVAILABLE", "transaction manager is unavailable")
        if request.arguments:
            raise HarnessError("INVALID_ARGUMENT", "transaction commands do not accept arguments")
        if request.command == "transaction.begin":
            result = self.transactions.begin(request.transaction_id, scene_revision=self.scene_revision)
        elif request.command == "transaction.commit":
            result = self.transactions.commit(request.transaction_id, scene_revision=self.scene_revision)
            self._approved_snapshots[result["snapshotId"]] = self.scene_revision
        elif request.command == "transaction.rollback":
            result = self.transactions.rollback(request.transaction_id)
            self.scene_revision = result["beginRevision"]
        else:
            raise HarnessError("UNKNOWN_COMMAND", f"unknown command: {request.command}")
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "requestId": request.request_id,
            "status": "succeeded",
            "sceneRevision": self.scene_revision,
            "changedObjects": [],
            "warnings": [],
            "snapshotId": result["snapshotId"],
            "result": result,
        }

    def _handle_authorize(self, request: CommandRequest) -> dict:
        arguments = request.arguments
        unknown = sorted(set(arguments) - {"action", "requestId", "userConfirmed", "ttlSeconds"})
        if unknown:
            raise HarnessError("INVALID_ARGUMENT", f"unknown authorization fields: {unknown}")
        if arguments.get("userConfirmed") is not True:
            raise HarnessError("USER_CONFIRMATION_REQUIRED", "explicit user confirmation is required")
        action = arguments.get("action")
        target_request_id = arguments.get("requestId")
        if action not in GATED_COMMANDS or not isinstance(target_request_id, str) or not target_request_id:
            raise HarnessError("INVALID_ARGUMENT", "authorization requires a gated action and target requestId")
        ttl = min(300, max(1, int(arguments.get("ttlSeconds", 60))))
        claim = self.authorization.issue(target_request_id, action, ttl_seconds=ttl)
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "requestId": request.request_id,
            "status": "succeeded",
            "sceneRevision": self.scene_revision,
            "changedObjects": [],
            "warnings": [],
            "result": {"authorization": claim, "action": action, "targetRequestId": target_request_id, "ttlSeconds": ttl},
        }

    def _remember(self, request_id: str, response: dict) -> None:
        if not request_id:
            return
        self._responses[request_id] = copy.deepcopy(response)
        self._responses.move_to_end(request_id)
        while len(self._responses) > self._replay_limit:
            self._responses.popitem(last=False)

    def _record_audit(self, payload: dict, response: dict) -> None:
        sanitized = dict(payload) if isinstance(payload, dict) else {"request": "invalid"}
        if "authorization" in sanitized:
            sanitized["authorization"] = "[REDACTED]"
        sanitized["status"] = response["status"]
        sanitized["sceneRevision"] = response["sceneRevision"]
        sanitized["executionPolicy"] = self.execution_policy.to_audit_dict()
        self._audit.append(sanitized)

    def audit_entries(self) -> list[dict]:
        return copy.deepcopy(self._audit)
