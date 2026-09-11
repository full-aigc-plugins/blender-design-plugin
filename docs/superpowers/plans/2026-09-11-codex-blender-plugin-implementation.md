# Codex Blender Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe Codex-to-Blender preview export plugin with structured receipts and deterministic restoration.

**Architecture:** Codex Skills invoke a Python runner, which starts a user-installed Blender background process and a narrow scene bridge. The bridge produces local artifacts and receipts; no cloud integration exists in this repository.

**Tech Stack:** Codex plugin manifest, Agent Skills, Python 3, Blender Python API, JSON Schema, unittest/pytest, optional ffprobe.

**Spec:** `docs/superpowers/specs/2026-09-11-codex-blender-plugin-design.md`

## Global Constraints

- Plugin ID is `codex-blender` and display name is `Codex Blender`.
- Use argv arrays; never execute interpolated shell command strings.
- Do not install or bundle Blender, ffmpeg, packages, or vendor code.
- Do not perform remote upload or paid generation.
- Every scene mutation has a tested restoration path.
- Real runtime support is claimed only for tested Blender/OS combinations.

---

### Task 1: Plugin and receipt contracts

**Files:** Create `.codex-plugin/plugin.json`, `schemas/scene_receipt.schema.json`, `schemas/artifact_receipt.schema.json`, `tests/test_contracts.py`.

- [ ] Write failing tests asserting plugin identity, closed receipt schemas, path/hash/media fields, and rejection of unknown fields.
- [ ] Run `python3 -m unittest tests/test_contracts.py -v`; expect failures because manifests and schemas do not exist.
- [ ] Implement the minimum manifest and schemas.
- [ ] Re-run the focused tests and plugin validator; expect PASS.
- [ ] Commit with `feat: define Blender plugin contracts`.

### Task 2: Capability probe and safe runner

**Files:** Create `scripts/blender_runner.py`, `tests/test_blender_runner.py`.

- [ ] Write failing tests for executable discovery, version parsing, argv construction, timeout, cancellation, and path containment.
- [ ] Run `python3 -m unittest tests/test_blender_runner.py -v`; confirm behavior failures.
- [ ] Implement `discover_blender()`, `build_argv()`, and `run_blender()` without shell execution.
- [ ] Re-run focused and contract tests; expect PASS.
- [ ] Commit with `feat: add safe Blender process runner`.

### Task 3: Scene inspection bridge

**Files:** Create `scripts/blender_bridge.py`, `tests/fakes/fake_bpy.py`, `tests/test_scene_inspection.py`.

- [ ] Write failing tests for cameras, frame range, resolution, materials, warnings, and disabled auto-execution.
- [ ] Run the tests and confirm missing inspection behavior.
- [ ] Implement read-only `inspect_scene()` returning `SceneReceipt`.
- [ ] Re-run tests; expect PASS with no scene mutations.
- [ ] Commit with `feat: inspect Blender scenes`.

### Task 4: Reversible preview export

**Files:** Modify `scripts/blender_bridge.py`; create `tests/test_preview_export.py`.

- [ ] Write failing tests for white-model, material-preview, output path, and restoration after success and injected failures.
- [ ] Confirm RED, including a state diff proving restoration currently fails.
- [ ] Implement snapshot/configure/render/restore with restoration in `finally`.
- [ ] Re-run tests and assert pre/post state equality.
- [ ] Commit with `feat: export reversible Blender previews`.

### Task 5: Media validation and receipts

**Files:** Create `scripts/media_probe.py`, `tests/test_media_probe.py`.

- [ ] Write failing tests for codec, dimensions, fps, duration, size, SHA-256, partial files, and missing ffprobe.
- [ ] Confirm RED, then implement validation with dependency detection and no installation.
- [ ] Re-run focused and regression tests; expect PASS.
- [ ] Commit with `feat: validate Blender preview artifacts`.

### Task 6: Agent Skills and recovery workflows

**Files:** Create `skills/codex-blender-use/`, `skills/codex-blender-inspect/`, `skills/codex-blender-export-preview/`, `skills/codex-blender-validate-media/` and behavioral fixtures.

- [ ] Run no-skill scenarios showing unsafe mutation, silent install, or unverified completion decisions.
- [ ] Write each Skill separately, validating it before moving to the next.
- [ ] Run quick validation and TRACE checks for every Skill.
- [ ] Run forward scenarios proving approvals, restoration, and evidence boundaries.
- [ ] Commit with `feat: add Codex Blender workflows`.

### Task 7: Runtime and distribution gates

**Files:** Create `.agents/plugins/marketplace.json`, `scripts/validate_distribution.py`, `tests/test_distribution.py`, `docs/verification/blender-runtime.md`.

- [ ] Write failing distribution tests for identity, paths, secrets, Skill count, and marketplace source.
- [ ] Implement the repository marketplace and validator.
- [ ] Run all offline tests, `git diff --check`, plugin validation, and secret scans.
- [ ] With explicit user authorization and a known Blender path, run one fixture smoke test and record the exact version; otherwise mark runtime acceptance blocked.
- [ ] Commit with `test: verify Codex Blender distribution`.
