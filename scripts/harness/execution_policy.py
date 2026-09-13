"""User-interaction policy for a bounded Blender design run.

The policy decides which lifecycle events require a conversational review. It
does not grant command authorization: path checks, transactions, and
action-bound claims remain enforced by the Harness session.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum


class ExecutionPolicyError(ValueError):
    """Raised when an automatic-run envelope is incomplete or unsafe."""


class ExecutionMode(str, Enum):
    """Supported user-interaction cadences."""

    INTERACTIVE = "interactive"
    AUTO_WITH_BUDGET = "auto_with_budget"
    REVIEW_ONLY = "review_only"


_IRREVERSIBLE_EVENTS = frozenset(
    {"delete", "overwrite", "expert_python", "path_escape", "budget_exceeded", "recovery_resubmit"}
)


@dataclass(frozen=True)
class ExecutionPolicy:
    """Immutable execution envelope recorded with each design session."""

    mode: ExecutionMode
    approved_output_root: str | None = None
    allow_designed_proxies: bool = False
    downstream_budget_limit: Decimal | None = None

    @classmethod
    def interactive(cls) -> "ExecutionPolicy":
        """Create a policy that requests normal milestone review."""
        return cls(ExecutionMode.INTERACTIVE)

    @classmethod
    def review_only(cls) -> "ExecutionPolicy":
        """Create a policy that permits no mutation or export."""
        return cls(ExecutionMode.REVIEW_ONLY)

    @classmethod
    def auto_with_budget(
        cls,
        approved_output_root: str | None,
        allow_designed_proxies: bool,
        downstream_budget_limit: str | Decimal | None,
    ) -> "ExecutionPolicy":
        """Create an automatic policy constrained to one output root and budget."""
        if not isinstance(approved_output_root, str) or not approved_output_root.strip():
            raise ExecutionPolicyError("auto_with_budget requires approved_output_root")
        budget = cls._parse_budget(downstream_budget_limit)
        return cls(
            ExecutionMode.AUTO_WITH_BUDGET,
            approved_output_root=approved_output_root,
            allow_designed_proxies=bool(allow_designed_proxies),
            downstream_budget_limit=budget,
        )

    @staticmethod
    def _parse_budget(value: str | Decimal | None) -> Decimal | None:
        if value is None:
            return None
        try:
            budget = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ExecutionPolicyError("downstream_budget_limit must be decimal") from exc
        if not budget.is_finite() or budget < 0:
            raise ExecutionPolicyError("downstream_budget_limit must be non-negative")
        return budget

    def requires_user_review(self, event: str) -> bool:
        """Return whether the named lifecycle event interrupts this policy."""
        if event in _IRREVERSIBLE_EVENTS:
            return True
        if self.mode is ExecutionMode.INTERACTIVE:
            return True
        if self.mode is ExecutionMode.REVIEW_ONLY:
            return True
        return False

    def to_audit_dict(self) -> dict[str, object]:
        """Return a non-secret, JSON-safe policy record for the session audit."""
        return {
            "mode": self.mode.value,
            "approvedOutputRoot": self.approved_output_root,
            "allowDesignedProxies": self.allow_designed_proxies,
            "downstreamBudgetLimit": (
                str(self.downstream_budget_limit) if self.downstream_budget_limit is not None else None
            ),
        }
