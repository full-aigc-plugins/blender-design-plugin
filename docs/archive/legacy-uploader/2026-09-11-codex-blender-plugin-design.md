# Codex Blender Plugin Design

## Goal

Deliver an installable Codex plugin that safely inspects authorized Blender projects and exports validated local preview videos through reversible Blender automation.

## Required behavior

- Discover Blender without installing it.
- Inspect before mutation and return a structured scene receipt.
- Require explicit project and output scopes.
- Export white-model or material-preview video from a selected camera and frame range.
- Restore every temporary scene setting on success, failure, cancellation, and timeout.
- Validate the final media and emit an artifact receipt usable by `dreamina-3d`.

## Non-goals

No remote upload, paid generation, arbitrary add-on execution, vendor source reuse, bundled Blender, or bundled ffmpeg.

## Acceptance

All schema, path, fake-bpy, restoration, media, and plugin-package tests pass. A real Blender smoke test is a separate environment gate and cannot be inferred from unit tests.

---

## Revision 2 (2026-09-12): reuse-based Codex integration

**This revision supersedes the clean-room constraint and the vendoring prohibition below.**
The `jimeng_blender_uploader` 1.0.0 add-on (macOS/CN build) already implements the render,
encode, preview-mode, and upload behaviour this plugin needs. Re-implementing it was the wrong
call: the deliverable is the **Codex integration** around that implementation, not a second
copy of it.

**Changed:** the plugin vendors the add-on's headless core instead of reimplementing it, and
the Jimeng link/upload flow is **in scope** rather than assigned away to `dreamina-3d`. The
design/implementation sections above still describe the surrounding contracts (receipts,
inspection, safe process launch, distribution) and remain in force.

**Vendored verbatim** into `vendor/jimeng_blender_uploader/`, with upstream SHA-256 recorded
and asserted by a test: `dcc_config.py`, `upload_bridge.py`, `settings.py`, `variant.py`,
`viewport_render.py`. Our own minimal `__init__.py` replaces the upstream one, because the
upstream `__init__.py` is the Blender UI registration and importing it headless would fail.

**Excluded:** `panel.py`, `operators.py`, `state.py` and the upstream `__init__.py` (the
Blender sidebar UI a Codex flow does not use), the legacy Node helper
`helpers/jimeng_upload/`, and the packaged ~120 MB `runtime/ffmpeg/*` binaries — ffmpeg
resolution falls through to a system installation and is never bundled here.

**Still ours:** the plugin manifest, the closed receipt schemas and their validator, the
safe process runner, read-only scene inspection, the headless adapter that feeds the vendored
render core without the add-on's UI properties, media validation and the artifact receipt,
and the Codex Skills that route user intent.

**Non-goals now reduced:** "no remote upload" and "no vendor code reuse" are withdrawn as
non-goals, by explicit user decision. Still excluded: paid generation, bundling Blender or
ffmpeg, and executing untrusted `.blend` scripts without authorization.

**Known limitation to carry:** the vendored `variant.py` is a *generated* build artefact and
pins region `cn`, platform `mac`, language `zh_cn`. It is vendored verbatim as the baseline;
other regions/platforms are not covered by this revision.

---

## Revision 3 (2026-09-12): operator-level reuse

Revision 2 still duplicated orchestration that already existed in the official add-on. The
current implementation therefore vendors the complete upstream Python/UI package and legacy
helper directory byte-for-byte, excluding only the bundled ffmpeg runtime, and registers it
inside Blender. `scripts/codex_bridge.py` sets the same scene inputs as the official panel and
calls `bpy.ops.jimeng.render_upload()` or `bpy.ops.jimeng.upload_existing()` directly.

Codex-owned behavior is limited to safe process launch, project/output scope checks, read-only
scene inspection, result projection, and post-run restoration observation. Protocol fetching,
frame validation, rendering, encoding, file-size validation, link creation, state, caching, and
user-facing error taxonomy remain upstream-owned. The complete 13-file provenance inventory is
recorded in `vendor/jimeng_blender_uploader/UPSTREAM.md`.
