# Dreamina 3D Preview Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a preview-only Blender adapter executable that satisfies the `codex-dreamina-3d` argv/JSON contract without uploading or invoking paid generation.

**Architecture:** A thin executable parses the shared adapter CLI and delegates to a focused Python module. That module uses the existing safe Blender runner, Workbench standard background rendering plus the vendored ffmpeg sequence encoder, media probing, and atomic receipt/status files; the existing Jimeng link flows are unchanged.

**Tech Stack:** Python 3, Blender 5.2.1 LTS Python API, vendored viewport renderer, ffprobe, JSON, unittest.

**Spec:** `docs/superpowers/specs/2026-09-13-dreamina-3d-preview-adapter-design.md`

## Global Constraints

- Never call the Jimeng upload bridge, Dreamina CLI, or a paid/network generation API.
- Perform at most one render attempt per request; status reconciliation is read-only.
- Use argv arrays, atomic JSON writes, validated paths, and confirmed restoration.
- Do not modify the existing camera-render or local-upload behavior.
- Maya is out of scope.

---

### Task 1: Adapter CLI and durable status contract

**Files:**
- Create: `scripts/blender_adapter.py`
- Create: `bin/blender_adapter`
- Create: `tests/test_blender_adapter.py`

**Interfaces:**
- Consumes: `--request PATH --receipt PATH --output PATH [--inspect|--status]`.
- Produces: exit code plus atomic receipt/status JSON.

- [x] Write tests that execute the real CLI wrapper and assert argument validation, inspect dispatch, export dispatch, and query-only status behavior.
- [x] Run `python3 -m unittest tests.test_blender_adapter -v` and confirm failure because the adapter does not exist.
- [x] Implement argument parsing, safe path checks, atomic JSON persistence, stable JSON errors, and read-only `--status`.
- [x] Run the focused tests and confirm they pass.

### Task 2: Preview-only Blender bridge and shared receipt

**Files:**
- Create: `scripts/preview_only_bridge.py`
- Modify: `scripts/blender_adapter.py`
- Extend: `tests/test_blender_adapter.py`

**Interfaces:**
- Consumes: normalized scene/camera/frame/output request.
- Produces: shared `ArtifactReceipt` version `1.0.0` after media verification.

- [x] Write tests proving the Blender-side flow uses `bpy.ops.render.render(write_still=True)` plus the vendored sequence encoder, but never `bpy.ops.render.opengl`, `start_local_bridge`, `render_upload`, or `upload_existing`.
- [x] Write tests for output mismatch, malformed media, unconfirmed restoration, timeout, and duplicate status query without re-render.
- [x] Run the focused tests and confirm the expected RED failures.
- [x] Implement the preview-only bridge, ffprobe-backed media metadata, SHA-256/stat verification, receipt normalization, and fail-closed restoration.
- [x] Run the focused tests and the existing Blender suite.

### Task 3: Cross-plugin discovery and real Blender acceptance

**Files:**
- Modify: `.codex-plugin/plugin.json`
- Modify: `scripts/validate_distribution.py`
- Modify: `docs/verification/blender-runtime.md`
- Modify: `docs/verification/offline.md`
- Test: `tests/test_distribution.py`
- Test: `/Users/wandl/workspaces/workspace-partme-ai/codex-dreamina-3d-plugin/tests/test_three_package_validation.py`

**Interfaces:**
- Consumes: `codex-dreamina-3d` companion discovery and DCC handoff.
- Produces: discoverable executable plus recorded Blender 5.2.1 runtime evidence.

- [x] Write distribution and cross-plugin tests that fail until `bin/blender_adapter` is executable and advertises receipt contract `1.0.0`.
- [x] Add the manifest contract declaration and distribution validation.
- [x] Run `codex-dreamina-3d` capability discovery and its Blender fixture handoff through the real adapter executable.
- [x] Run one authorized Blender 5.2.1 LTS preview-only smoke test and record exact artifact/hash/restoration evidence; do not run Maya or paid Seedance.
- [x] Run both repositories' full suites, validators, secret scans, and `git diff --check`.
