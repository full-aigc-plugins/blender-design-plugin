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

## Foundation baseline completed 2026-09-12

The repository already contains the validated `codex-blender` compatibility manifest, URL marketplace entry, Apache-2.0/legal files, transparent brand assets, implementation directories, distribution validator, and RED/GREEN foundation tests. Tasks below must extend these files rather than recreate or overwrite them. This baseline does not implement or validate Blender runtime workflows.

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

---

## Detailed executor contract

The task summaries above define review boundaries. Implementers must follow the concrete steps below; a later task must not begin until the preceding task has a clean review.

### Task 1 detailed steps — package identity and schemas

**Files:**

- Create: `.codex-plugin/plugin.json`
- Create: `.agents/plugins/marketplace.json`
- Create: `schemas/scene_receipt.schema.json`
- Create: `schemas/artifact_receipt.schema.json`
- Create: `tests/test_contracts.py`
- Create: `scripts/validate_distribution.py`

**Produces:** schema version `codex-blender.receipt/v1`; plugin ID `codex-blender`; Python function `validate_document(schema_name: str, payload: dict) -> list[str]`.

- [ ] Create `tests/test_contracts.py` first with fixtures that require `additionalProperties: false`, a 64-character lowercase SHA-256, positive media dimensions, and `restoration.status` in `confirmed|failed|unknown`.
- [ ] Run `python3 -m unittest tests/test_contracts.py -v`; record missing manifest/schema failures as RED.
- [ ] Implement manifest metadata with design-stage version `0.1.0`, no fake MCP server, `skills: "./skills/"`, and display name `Codex Blender`.
- [ ] Define `SceneReceipt` required fields: `schemaVersion`, `producer`, `blenderVersion`, `projectFingerprint`, `cameras`, `frameRange`, `resolution`, `previewModes`, `warnings`.
- [ ] Define `ArtifactReceipt` required fields: `schemaVersion`, `producer`, `path`, `sha256`, `codec`, `width`, `height`, `fps`, `durationSeconds`, `bytes`, `camera`, `frameRange`, `previewMode`, `restoration`.
- [ ] Run contract tests, plugin validation, and `python3 scripts/validate_distribution.py`; record GREEN.
- [ ] Commit only Task 1 files.

### Task 2 detailed steps — discovery and process isolation

**Files:**

- Create: `scripts/blender_runner.py`
- Create: `tests/test_blender_runner.py`

**Interface:**

```python
@dataclass(frozen=True)
class BlenderRuntime:
    executable: Path
    version: str
    background_supported: bool

def discover_blender(explicit_path: str | None, search_path: str) -> BlenderRuntime: ...
def build_argv(runtime: BlenderRuntime, project: Path, request: Path) -> list[str]: ...
def run_blender(argv: list[str], timeout_seconds: int) -> CompletedProcess[str]: ...
```

- [ ] Write RED tests for explicit executable precedence, PATH discovery, missing executable, version output parsing, paths containing spaces/Unicode, and rejection of symlink escapes.
- [ ] Add a subprocess spy proving `shell=False`, an allowlisted environment, captured stdout/stderr, and bounded timeout.
- [ ] Implement discovery without modifying PATH or installing Blender.
- [ ] Implement cancellation so the child receives graceful termination before forced kill; return `TIMEOUT` or `CANCELLED` without retry.
- [ ] Run `python3 -m unittest tests/test_blender_runner.py tests/test_contracts.py -v` and commit.

### Task 3 detailed steps — read-only scene inspection

**Files:**

- Create: `scripts/blender_bridge.py`
- Create: `tests/fakes/fake_bpy.py`
- Create: `tests/test_scene_inspection.py`

**Interface:**

```python
def inspect_scene(bpy_module, approved_project: Path) -> dict: ...
def main(request_path: str) -> int: ...
```

- [ ] Build fake scenes with zero/one/multiple cameras, invalid frame ranges, percentage-scaled resolution, no materials, colored materials, image textures, unsupported nodes, and linked assets outside scope.
- [ ] Capture a serialized scene state before inspection and assert byte-equivalent state afterward.
- [ ] Implement inspection with no operators that mutate selection or mode.
- [ ] Emit one JSON receipt to stdout and redacted diagnostics to stderr; never print the project contents or environment.
- [ ] Run the focused tests twice to prove deterministic receipts and commit.

### Task 4 detailed steps — reversible preview rendering

**Files:**

- Modify: `scripts/blender_bridge.py`
- Create: `tests/test_preview_export.py`

**Interface:**

```python
@contextmanager
def restored_scene_state(bpy_module): ...
def export_preview(bpy_module, request: dict) -> dict: ...
```

- [ ] Write RED tests that inject failures before configuration, during frame rendering, during media assembly, and after artifact creation.
- [ ] Snapshot render engine, output path, file format, resolution, percentage, fps, frame range, active camera, shading mode, material overrides, selection, active object, mode, and current frame.
- [ ] Implement `white_model`, `material_preview`, and `existing_video` branches; `existing_video` must not open or mutate the scene.
- [ ] Write to a unique temporary directory and atomically move only a validated final artifact.
- [ ] Assert restoration after every terminal path, including `KeyboardInterrupt` and timeout cleanup.
- [ ] Run `python3 -m unittest tests/test_preview_export.py tests/test_scene_inspection.py -v` and commit.

### Task 5 detailed steps — media validation

**Files:**

- Create: `scripts/media_probe.py`
- Create: `tests/test_media_probe.py`

**Interface:**

```python
def discover_ffprobe(explicit_path: str | None) -> Path | None: ...
def probe_media(path: Path, ffprobe: Path | None) -> dict: ...
def validate_media(probe: dict, profile: dict) -> list[str]: ...
```

- [ ] Use synthetic ffprobe JSON for H.264 success, wrong codec, odd dimensions, zero duration, excessive duration, fps mismatch, empty/partial file, and size overflow.
- [ ] Prove missing ffprobe produces `DEPENDENCY_MISSING` and never installs software.
- [ ] Hash the final bytes after validation; reject files changed between probe and hash using pre/post stat checks.
- [ ] Run focused tests and all Python tests; commit.

### Task 6 detailed steps — Agent Skills

**Files:**

- Create: `skills/codex-blender-use/SKILL.md`
- Create: `skills/codex-blender-inspect/SKILL.md`
- Create: `skills/codex-blender-export-preview/SKILL.md`
- Create: `skills/codex-blender-validate-media/SKILL.md`
- Create: `tests/scenarios/*.md`

- [ ] Run and save no-skill baselines for: missing Blender, untrusted embedded scripts, absent camera, output outside scope, render timeout, and request to upload remotely.
- [ ] Implement `codex-blender-use` as the router; it must not duplicate the three capability Skills.
- [ ] Implement inspect, export, and validation Skills one at a time; after each, run quick validation, its matching scenario, and strict TRACE.
- [ ] Verify the router selects `existing_video` without opening Blender and rejects remote-upload ownership.
- [ ] Run all forward scenarios with fresh contexts and commit.

### Task 7 detailed steps — release evidence

**Files:**

- Create: `tests/test_distribution.py`
- Create: `docs/verification/offline.md`
- Create: `docs/verification/blender-runtime.md`
- Modify: `.agents/plugins/marketplace.json`

- [ ] Test repository URL `https://github.com/partme-ai/codex-blender-plugin.git`, ID, version, four-Skill inventory, links, licenses, no symlinks, and secret patterns.
- [ ] Run `python3 -m unittest discover -s tests -v`, quick validation for every Skill, plugin validator, link checker, secret scan, and `git diff --check`.
- [ ] Record offline evidence without upgrading it to Blender runtime evidence.
- [ ] If the user supplies an authorized Blender executable, run a fixture scene with no network and compare pre/post scene state plus media receipt; otherwise record `runtimeAcceptance=BLOCKED_MISSING_AUTHORIZED_RUNTIME`.
- [ ] Install through a local marketplace only after validation, test in a new Codex task, and record source/cache byte parity.
- [ ] Commit verification evidence and stop for branch integration choice.

## Completion gate

```text
contract_tests = PASS
runner_tests = PASS
scene_inspection_tests = PASS
restoration_tests = PASS
media_tests = PASS
skill_quick_validation = 4/4
skill_trace = 4/4
plugin_validation = PASS
secret_matches = 0
runtime_acceptance = PASS or explicitly BLOCKED
```
