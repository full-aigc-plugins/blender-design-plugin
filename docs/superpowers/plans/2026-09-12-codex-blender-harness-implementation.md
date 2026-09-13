# Codex Blender Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Dreamina-uploader adapter with a dual-mode, transactional Blender Harness that lets Codex design scenes and export verified files.

**Architecture:** A transport-neutral Harness core runs inside Blender and executes closed JSON commands on Blender's main thread. Managed bootstrap and Connector Add-on modes share the same session, command, transaction, preview, and export components. An external CLI adapter gives Codex and `codex-dreamina-3d` a stable argv + JSON contract.

**Tech Stack:** Python 3, Blender 5.x Python API, Unix Domain Sockets, Windows Named Pipes, loopback TCP fallback, JSON Schema, unittest, ffprobe.

**Spec:** `docs/superpowers/specs/2026-09-12-codex-blender-harness-design.md`

## Global Constraints

- macOS Apple Silicon and Windows x64 are release gates; Linux is experimental.
- Managed mode must not install or modify Blender preferences.
- Connector mode contains no Dreamina behavior.
- All mutations run on Blender's main thread through a queue.
- Unknown commands, stale revisions, duplicate non-idempotent requests, and path escapes fail closed.
- Destructive actions, overwrites, final export, and expert Python require action-bound authorization.
- No Jimeng/Dreamina link, credential, quote, submit, query, or paid-generation behavior remains.
- Existing user changes and unrelated worktree edits must be preserved.

---

### Task 1: Replace plugin contracts and identity

**Files:** Modify `.codex-plugin/plugin.json`, `README.md`, `README.zh-CN.md`, receipt schemas, distribution tests; create protocol schemas.

**Produces:** accurate product metadata plus closed `command`, `response`, `milestone_receipt`, and generalized `artifact_receipt` schemas.

- [ ] Write RED contract tests rejecting Dreamina/Jimeng claims and accepting the new closed documents.
- [ ] Run focused tests and confirm failures reflect old metadata/schema shapes.
- [ ] Implement the minimum schema and manifest changes.
- [ ] Run contract and distribution tests; update documentation entry points.
- [ ] Commit `feat: redefine Codex Blender harness contracts`.

### Task 2: Session, revision, idempotency, and authorization core

**Files:** Create `scripts/harness/{errors,protocol,authorization,session}.py`; create focused tests.

**Produces:** `HarnessSession.handle(request) -> response`, revision checks, request replay cache, action-bound authorization.

- [ ] Write RED tests for malformed requests, unknown versions, duplicate IDs, stale revisions, token expiry, command/action mismatch, and audit redaction.
- [ ] Implement immutable request parsing and typed error responses.
- [ ] Implement session revision and bounded idempotency cache.
- [ ] Implement HMAC authorization claims without logging secrets.
- [ ] Run focused tests and commit `feat: add transactional harness session core`.

### Task 3: Command registry and Blender main-thread queue

**Files:** Create `scripts/harness/{registry,main_thread}.py`; extend fake bpy support and tests.

**Produces:** `CommandRegistry`, command metadata, guarded dispatch, `MainThreadExecutor`.

- [ ] Write RED tests proving transport threads cannot mutate bpy and timer execution occurs on the owning thread.
- [ ] Add closed command registration with argument validators and risk classification.
- [ ] Implement queue, timeout, cancellation, and structured result propagation.
- [ ] Test injected command failures and commit `feat: execute Blender commands on the main thread`.

### Task 4: Scene and object design commands

**Files:** Create `scripts/harness/commands/{scene,object,modifier}.py`; create command tests.

**Produces:** inspect/new/open/save/save-as, collection management, primitives/curves/text, transforms, hierarchy, duplicate/rename/delete, common modifiers.

- [ ] Write RED behavior tests against fake bpy for each command and authorization boundary.
- [ ] Implement non-destructive commands first, then gated destructive commands.
- [ ] Assert changed datablocks, revision increments, and deterministic scene summaries.
- [ ] Run focused tests and commit `feat: add Blender scene and modeling commands`.

### Task 5: Materials, cameras, lights, and animation

**Files:** Create `scripts/harness/commands/{material,camera,light,animation}.py`; create tests.

**Produces:** PBR material creation/assignment, approved textures, camera composition, lighting/world settings, frame range/keyframes/interpolation.

- [ ] Write RED tests including missing texture, invalid color/vector, absent object, and stale revision cases.
- [ ] Implement minimum stable Blender API mappings.
- [ ] Validate postconditions and scene summaries.
- [ ] Run focused tests and commit `feat: add lookdev camera lighting and animation commands`.

### Task 6: Snapshot, rollback, and recovery

**Files:** Create `scripts/harness/{snapshot,transaction,recovery}.py`; create failure-injection tests.

**Produces:** begin/commit/rollback, persistent `.blend` checkpoints, crash recovery metadata.

- [ ] Write RED tests for failure before mutation, mid-batch, after save, cancellation, and stale checkpoint.
- [ ] Implement lightweight state snapshots and persistent checkpoint boundaries.
- [ ] Restore every field independently and report confirmed/failed restoration.
- [ ] Test replay of committed idempotent commands only and commit `feat: add Blender transaction recovery`.

### Task 7: Preview and milestone receipts

**Files:** Create `scripts/harness/{preview,milestone}.py`; create Blender fixtures and tests.

**Produces:** camera/front/side/top PNGs, animation first/middle/last samples, `MilestoneReceipt`.

- [ ] Write RED tests for fresh-image hashes, view naming, revision binding, and missing camera fallback.
- [ ] Implement UI-context viewport capture with offline render fallback where supported.
- [ ] Emit deterministic scene summary and warnings.
- [ ] Run fake and real Blender smoke tests; commit `feat: add visual milestone evidence`.

### Task 8: Multi-format export and artifact validation

**Files:** Create `scripts/harness/{exporter,artifact_validator}.py`; create export tests and fixtures.

**Produces:** `.blend`, `.glb`, `.gltf`, `.fbx`, `.obj`, `.stl`, `.png`, `.jpg`, H.264 `.mp4`, closed artifact receipts.

- [ ] Write RED tests for format routing, overwrite authorization, path containment, hashes, media probes, and re-import validation.
- [ ] Implement exporters using supported Blender operators and explicit context setup.
- [ ] Implement isolated re-import structural validation and ffprobe media validation.
- [ ] Run per-format real Blender tests on macOS; record Windows as required external gate.
- [ ] Commit `feat: export and validate Blender artifacts`.

### Task 9: Managed mode and transport layer

**Files:** Create `scripts/harness/{transport,server}.py`, `scripts/managed_bootstrap.py`, `scripts/harness_cli.py`; create transport/conformance tests.

**Produces:** UDS, Named Pipe abstraction, authenticated TCP fallback, managed Blender lifecycle, CLI adapter.

- [ ] Write RED tests for permissions, random secret, wrong token, size limits, idle expiry, reconnect, and graceful shutdown.
- [ ] Implement managed launch without Blender preference changes.
- [ ] Implement CLI status/command/inspect/export interface with JSON stdout and diagnostics stderr.
- [ ] Run macOS real session conformance and commit `feat: add non-invasive managed Blender mode`.

### Task 10: Connector Add-on mode

**Files:** Create `connector/codex_blender_connector/{__init__,panel,preferences,runtime}.py`; create packaging and conformance tests.

**Produces:** installable Connector zip with visible status/start/stop/revoke controls using the shared Harness.

- [ ] Write RED tests for registration, no autostart without consent, revoke, file-change authorization invalidation, and package contents.
- [ ] Implement the lightweight Add-on without duplicating Harness commands.
- [ ] Run the same protocol conformance suite against Connector mode.
- [ ] Perform real Blender UI smoke test and commit `feat: add Blender Connector mode`.

### Task 11: Agent Skills and milestone workflow

**Files:** Replace existing Skills with router, managed, connector, design, preview, export, and recovery Skills; update scenario tests.

**Produces:** user-intent routing and milestone-driven design workflow with no Dreamina ownership.

- [ ] Write RED tests proving Jimeng/link language is absent and both modes route correctly.
- [ ] Implement Skills with progressive disclosure and exact command boundaries.
- [ ] Run scenario, official structure, and TRACE checks after every Skill change.
- [ ] Commit `feat: add Codex Blender design workflows`.

### Task 12: Cross-plugin handoff and release gates

**Files:** Create `scripts/dreamina_adapter.py`; update verification docs, install guide, validators, and E2E tests.

**Produces:** preview adapter compatible with `codex-dreamina-3d`, macOS/Windows evidence matrix, accurate user documentation.

- [ ] Write RED handoff tests using the real receipt contract expected by `codex-dreamina-3d`.
- [ ] Implement inspect/export/status argv compatibility without importing the orchestrator.
- [ ] Run real macOS end-to-end through preview receipt validation; keep Dreamina paid submission out of scope.
- [ ] Record Windows x64 as a required external release gate until actually executed.
- [ ] Run all tests, distribution validation, secret scan, `git diff --check`, and docs link checks.
- [ ] Commit `test: verify Codex Blender harness distribution`.

## Completion gate

```text
managed_mode_macos = PASS
managed_mode_windows = PASS
connector_mode_macos = PASS
connector_mode_windows = PASS
protocol_conformance = PASS (both modes)
scene_design_commands = PASS
transaction_rollback = PASS
visual_milestones = PASS
release_export_formats = 9/9
dreamina_preview_handoff = PASS
skill_validation = PASS
secret_matches = 0
jimeng_or_dreamina_runtime_ownership = 0
```

## Execution ledger

| Task | Current evidence |
|---|---|
| 1 Contracts and identity | PASS — new manifest and four closed schemas |
| 2 Session core | PASS — revision, idempotency, HMAC authorization, redacted audit |
| 3 Registry and main thread | PASS — queue/thread tests and Blender timer server |
| 4 Scene/object commands | PASS — focused tests and real Blender command smoke |
| 5 Lookdev/camera/light/animation | PASS — focused tests and real Blender command smoke |
| 6 Snapshot/rollback | PASS macOS — persistent checkpoint and real failure rollback |
| 7 Visual milestones | PASS macOS — four fresh real Blender views and hashes |
| 8 Multi-format export | PASS macOS — all 9 formats pass; MP4 includes independent ffprobe evidence |
| 9 Managed mode | PASS macOS; Windows runtime not run |
| 10 Connector mode | PASS macOS; Windows runtime not run |
| 11 Agent Skills | Structure PASS; upstream quick validator blocked by missing `yaml` |
| 12 Cross-plugin/release | PARTIAL — product boundary passes; preview handoff and Windows gates remain |
