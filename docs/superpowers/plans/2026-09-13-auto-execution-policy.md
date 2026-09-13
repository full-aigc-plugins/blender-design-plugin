# Auto Execution Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a Blender request run through approved milestones without repeated user prompts while preserving destructive-action and output-path controls.

**Architecture:** Add a small policy value object outside the Blender runtime, then pass its immutable envelope into the session/audit layer and Skills. The Harness keeps transactions, previews, revisions, and authorizations unchanged; policy changes when to surface those facts to the user, not whether the facts are captured.

**Tech Stack:** Python 3, dataclasses, JSON-safe records, unittest, Codex Skills.

**Spec:** `docs/superpowers/specs/2026-09-12-codex-blender-harness-design.md`

## Global Constraints

- `auto_with_budget` never permits delete, overwrite, expert Python, or a path outside the approved root without an action-bound authorization.
- Missing references remain user-supplied unless the envelope allows identified Blender proxies.
- Every milestone still produces fresh evidence; the policy suppresses interruptions, not validation.
- Do not add downstream-rendering code to this plugin.

---

### Task 1: Define and validate the execution envelope

**Files:**
- Create: `scripts/harness/execution_policy.py`
- Modify: `scripts/harness/session.py`
- Test: `tests/test_execution_policy.py`

**Interfaces:**

```python
class ExecutionMode(str, Enum):
    INTERACTIVE = "interactive"
    AUTO_WITH_BUDGET = "auto_with_budget"
    REVIEW_ONLY = "review_only"

@dataclass(frozen=True)
class ExecutionPolicy:
    mode: ExecutionMode
    approved_output_root: str | None
    allow_designed_proxies: bool
    downstream_budget_limit: Decimal | None

    def requires_user_review(self, event: str) -> bool: ...
```

- [ ] **Step 1: Write failing policy tests**

```python
def test_auto_policy_suppresses_milestone_review_but_not_overwrite():
    policy = ExecutionPolicy.auto_with_budget("/tmp/out", False, "3.20")
    assert not policy.requires_user_review("milestone_complete")
    assert policy.requires_user_review("overwrite")
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python3 -m unittest tests.test_execution_policy -v`

- [ ] **Step 3: Implement immutable parsing and event decisions**

Implement `ExecutionMode`, `ExecutionPolicy`, JSON-safe serialization, and reject unknown modes, negative budgets, and an automatic policy without an approved output root.

- [ ] **Step 4: Bind policy to session audit metadata**

Extend `HarnessSession` construction with an optional `execution_policy`; include the scrubbed policy envelope in audit records without weakening `AuthorizationManager` claim verification.

- [ ] **Step 5: Run focused tests**

Run: `python3 -m unittest tests.test_execution_policy tests.test_harness_session -v`

### Task 2: Add autonomous milestone reporting to Skills

**Files:**
- Modify: `skills/codex-blender-use/SKILL.md`
- Modify: `skills/codex-blender-design/SKILL.md`
- Modify: `docs/getting-started.zh-CN.md`
- Test: `tests/test_product_boundary.py`

**Interfaces:**

```text
auto_with_budget: accept one envelope, execute approved milestones, return one final artifact inventory.
interactive: retain explicit review.
review_only: do not mutate or export.
```

- [ ] **Step 1: Write a failing user-guide contract test**

Assert the guide describes the three modes, the one-time envelope, and the exception list.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python3 -m unittest tests.test_product_boundary.TestProductBoundary -v`

- [ ] **Step 3: Update Skills and guide**

Route `auto_with_budget` through all verified milestones and report only final artifacts plus deviations. Keep `interactive` as opt-in and prohibit any autonomous downstream upload.

- [ ] **Step 4: Run focused verification**

Run: `python3 -m unittest tests.test_product_boundary tests.test_distribution -v`

### Task 3: Regression validation

**Files:** No production changes.

- [ ] **Step 1: Run full suite**

Run: `python3 -m unittest discover -s tests -v`

- [ ] **Step 2: Validate distributable structure**

Run: `python3 scripts/validate_distribution.py`

- [ ] **Step 3: Check patch integrity**

Run: `git diff --check`

