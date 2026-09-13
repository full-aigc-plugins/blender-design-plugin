# Official Uploader One-Click Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver three explicit one-click Agent entry points for local Blender preview, official Jimeng Web handoff, and approved automatic Seedance generation.

**Architecture:** Extend the existing Blender Harness with runtime-only delegation to a user-installed official uploader, without bundling upstream source. Extend `codex-dreamina-3d` as the cross-plugin router: preview calls the Blender receipt adapter, web handoff calls the official-uploader Harness commands, and automatic generation calls the published Dreamina Design MCP lifecycle.

**Tech Stack:** Python 3, Blender Harness JSON protocol, Blender `bpy.ops`, Agent Skills, Dreamina Design MCP, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-13-official-uploader-dual-channel-design.md`

## Global Constraints

- Do not vendor, install, enable, or modify the official uploader.
- Do not reproduce its loopback bridge protocol or private upload implementation.
- Interactive completion is `JimengLinkReady`; automatic completion requires a verified final Seedance artifact.
- Official operator invocation and paid submission are at-most-once.
- Preview-only behavior and ArtifactReceipt `1.0.0` remain compatible.
- Maya and Windows runtime acceptance are outside this execution environment and remain explicit blockers.
- Preserve unrelated concurrent changes in the Dreamina Design repository.

---

### Task 1: Official uploader runtime delegation

**Files:**
- Create: `scripts/harness/commands/official_uploader.py`
- Modify: `scripts/harness/runtime.py`
- Test: `tests/test_official_uploader.py`

**Interfaces:**
- Produces: commands `official_uploader.inspect`, `official_uploader.render_and_link`, `official_uploader.link_existing`, `official_uploader.status`, `official_uploader.open_link`.
- Consumes: a running Connector Harness and the user-installed `jimeng_blender_uploader` operators.

- [x] Write RED tests for absent/incompatible add-on, capability projection, one render invocation, one local-video invocation, stale-link rejection, explicit open, and loopback-token redaction.
- [x] Run `python3 -m unittest tests.test_official_uploader -v` and confirm failures come from missing command implementation.
- [x] Implement runtime discovery and thin operator delegation without importing bundled upstream code.
- [x] Register read/gated risk levels in the existing command registry.
- [x] Run focused Harness and Connector regression tests.

### Task 2: Blender one-click Skills and packaging

**Files:**
- Create: `skills/codex-blender-jimeng-web/SKILL.md`
- Modify: `skills/codex-blender-use/SKILL.md`
- Modify: `.codex-plugin/plugin.json`
- Modify: `scripts/validate_distribution.py`
- Test: `tests/test_distribution.py`
- Test: `tests/test_product_boundary.py`

**Interfaces:**
- Produces: explicit intents `preview_only`, `jimeng_web`, and `downstream_seedance`.
- Consumes: Task 1 official-uploader commands and the existing preview/export Skills.

- [x] Write RED tests proving the router distinguishes all three intents and never describes a Jimeng link as generated media.
- [x] Implement the Jimeng Web Skill and update the Blender router.
- [x] Replace the obsolete blanket ban on Jimeng naming with the precise boundary: only runtime delegation Skill/command may name it.
- [x] Validate the plugin package and Skill inventory.

### Task 3: Dreamina 3D three-entry orchestration

**Files:**
- Modify: `/Users/wandl/workspaces/workspace-partme-ai/codex-dreamina-3d-plugin/skills/codex-dreamina-3d-use/SKILL.md`
- Create: `/Users/wandl/workspaces/workspace-partme-ai/codex-dreamina-3d-plugin/skills/codex-dreamina-3d-jimeng-web/SKILL.md`
- Create: `/Users/wandl/workspaces/workspace-partme-ai/codex-dreamina-3d-plugin/skills/codex-dreamina-3d-auto-seedance/SKILL.md`
- Modify: `/Users/wandl/workspaces/workspace-partme-ai/codex-dreamina-3d-plugin/.codex-plugin/plugin.json`
- Modify: `/Users/wandl/workspaces/workspace-partme-ai/codex-dreamina-3d-plugin/scripts/validate_distribution.py`
- Test: `/Users/wandl/workspaces/workspace-partme-ai/codex-dreamina-3d-plugin/tests/test_skills.py`

**Interfaces:**
- Produces: a single router with preview-only, Jimeng Web, and automatic Seedance routes.
- Consumes: Blender Harness/adapter and installed Dreamina Design MCP tools.

- [x] Write RED route tests including ambiguous intent, approval denial, existing submit ID, and final-artifact verification wording.
- [x] Implement the two bounded workflow Skills and update the router.
- [x] Ensure automatic mode calls capability/account, approved video submit, query-only recovery, download, and final hash verification.
- [x] Run Skill structure, scenario, TRACE, and fixture E2E tests.

### Task 4: Release refresh and acceptance

**Files:**
- Modify: both plugin manifests, marketplace metadata, READMEs, verification evidence, and version validators.
- Test: both complete repositories and distribution validators.

**Interfaces:**
- Produces: refreshed installed plugin snapshots and auditable GitHub release evidence.

- [x] Bump `codex-blender` and `codex-dreamina-3d` to the next compatible minor versions.
- [x] Run both full local suites, secret scans, link checks, and `git diff --check`.
- [x] Run real Blender preview-only acceptance and official-uploader discovery; if the official add-on is absent, record the exact blocker without installing it.
- [x] Re-query the existing successful Seedance submit ID and verify the downloaded artifact without new credit consumption.
- [ ] Commit and push each repository, wait for GitHub CI, reinstall from the configured marketplaces, and verify source/cache parity plus fresh Skill discovery.
