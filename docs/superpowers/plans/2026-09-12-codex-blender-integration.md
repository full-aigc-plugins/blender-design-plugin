# Codex Blender Integration Plan (Revision 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the official `jimeng_blender_uploader` render/encode/upload engine drivable from Codex, headlessly, with verified restoration and a validated artifact receipt.

**Architecture:** Codex Skills invoke a Python adapter. The adapter launches a user-installed Blender in background mode and, inside Blender, calls the **vendored** headless core of the official add-on to render and encode a preview, then drives the vendored upload bridge to produce a Jimeng link. Codex replaces the add-on's Blender sidebar UI; nothing else about the engine is rewritten.

**Tech Stack:** Codex plugin manifest, Agent Skills, Python 3, Blender Python API, vendored third-party modules, JSON Schema, unittest, system ffmpeg/ffprobe.

**Supersedes:** `docs/superpowers/specs/2026-09-11-codex-blender-plugin-design.md` § Revision 2, and the clean-room rule and vendoring prohibition of the 2026-09-11 plan (now historical). Tasks 1-3 of that plan are already merged on this branch and remain in force: the plugin manifest, the two closed receipt schemas + `validate_document`, `validate_distribution`, the safe process runner, and the read-only inspection bridge.

## Provenance facts (bind every task)

Upstream package: `jimeng_blender_uploader`, version **1.0.0**, macOS/CN build, obtained as
`jimeng_blender_uploader-mac-cn-1.0.0.zip`. Upstream SHA-256 of the five modules to vendor
verbatim — the vendoring task asserts these, and any later change is drift to be justified:

```
dcc_config.py        d559a7d3202a0621bc986e3069f6069d3a2c400908377fc521b6a20f75663cc4
upload_bridge.py     714d34aa2426e8a2f2fba61cb3fca54cf4f60e6252e7e79079b4471c68593393
settings.py          69454485ff3db83acb05145899af166398a132927b96203565ff42f78b598db8
variant.py           3e6fa3b54953634ff44aa3df0f00774ab7279644d8b12c3d49d8c4e174c7fba3
viewport_render.py   b9f1e6fcecd1ca704262f407fb9854540b37f6aab28a2635f3f0c8567f5f252b
```

The five are closed under imports (`viewport_render` needs `dcc_config`, `settings`,
`upload_bridge`; `settings` needs `variant`); nothing else is required, and none of them
imports `bpy`.

## Global Constraints

- Plugin ID is `codex-blender` and display name is `Codex Blender`.
- Use argv arrays; never execute interpolated shell command strings.
- Do not install or bundle Blender, ffmpeg, or packages. The vendored add-on ships ~120 MB of
  ffmpeg binaries; those binaries are **not** vendored, so ffmpeg resolution falls through to a
  system installation and a missing tool is a clean `DEPENDENCY_MISSING`, never a download.
- Never execute untrusted `.blend` scripts without explicit authorization; auto-execution stays
  disabled.
- Every scene mutation the vendored render core performs must be restored and the restoration
  verified, not assumed.
- Do not perform paid generation.
- Vendored files stay byte-identical to upstream except where this plan says otherwise; any
  deviation is recorded in `UPSTREAM.md` with a reason.
- Real runtime support is claimed only for tested Blender/OS combinations.
- `.superpowers/` is the SDD scratch workspace and is never committed.

## Upstream interop facts the tasks depend on

- Documented video profile: container `mp4`, codec `h264`, fps 24, duration 30 s,
  `min_frame_num` 44, `max_frame_num` 720, `file_size` 209715200 bytes.
- Resolution presets `360p|480p|720p|1080p|origin`; non-origin scales the **short edge**,
  preserves aspect, never upscales; dimensions are forced even.
- Encoding: libx264, `veryfast`, crf 20, `yuv420p`, TV range, `avc1` tag, `+faststart`, scale
  filter `scale=trunc(iw/2)*2:trunc(ih/2)*2:out_range=tv,format=yuv420p`; camera renders carry
  no audio; existing videos map `0:v:0` plus optional `0:a?` to AAC 128 kbps.
- Accepted as-is `.mp4`; converted `.mov`, `.webm`, `.avi`.
- Preview mode: material preview when a visible mesh owns a "non-default" material, else white
  model. Unsupported shader nodes are warnings, not failures.
- The local bridge serves the loopback resource-info payload the Jimeng page reads, and the
  redirect URL carries the channel and third-party identifiers.

---

### Task 1: Vendor the headless core with provenance

**Files:** Create `vendor/__init__.py`, `vendor/jimeng_blender_uploader/__init__.py`,
`vendor/jimeng_blender_uploader/{dcc_config.py,upload_bridge.py,settings.py,variant.py,viewport_render.py}`,
`vendor/jimeng_blender_uploader/UPSTREAM.md`, `tests/test_vendored_core.py`.

- [ ] Write the failing test first: assert `UPSTREAM.md` records all five upstream SHA-256 values, assert each vendored file hashes to its recorded value, and assert the package imports with `bpy` absent.
- [ ] Copy the five modules byte-for-byte from the official 1.0.0 package (sketchy mirror: the extracted archive staged outside the repo in the session's scratch directory).
- [ ] Write our own `vendor/jimeng_blender_uploader/__init__.py` containing no `bpy` import and no UI registration — the upstream one registers Blender operators and panels and cannot be imported headless.
- [ ] Record in `UPSTREAM.md`: package name, version, region/platform build, the five file hashes, the excluded files and why (`panel.py`, `operators.py`, `state.py`, upstream `__init__.py`, `helpers/jimeng_upload/`, `runtime/ffmpeg/*`), the license/provenance caveat, and the `variant.py` region/platform pin.
- [ ] Prove headless importability by importing the package in a child process where importing `bpy` raises.
- [ ] Commit with `feat: vendor jimeng uploader headless core`.

### Task 2: Headless export adapter over the vendored render core

**Files:** Modify `scripts/blender_bridge.py`; create `tests/test_preview_export.py`; extend `tests/fakes/fake_bpy.py`.

- [ ] Write failing tests for white-model, material-preview, and existing-video exports, output path containment, and restoration after success plus four injected failure points (before configuration, during frame rendering, during media assembly, after artifact creation).
- [ ] Confirm RED with a state diff proving restoration currently fails.
- [ ] Feed the vendored render core the inputs it reads from `scene.jimeng_*` without importing the upstream UI package, then call its render function unchanged.
- [ ] Return the honest artifact subset `{artifactPath, previewMode, camera, frameRange, restoration, bytes}`; do not claim ArtifactReceipt schema validity.
- [ ] Report `restoration.status` as `confirmed` only when the post-restore snapshot equals the pre-export snapshot; `failed` when it differs; `unknown` when no comparison was possible. One failing restore must not prevent the others.
- [ ] `existing_video` must not open or mutate the scene.
- [ ] Clean the temporary frame directory on every exit path, including when the render itself raises.
- [ ] Commit with `feat: export reversible Blender previews`.

### Task 3: Media validation, artifact receipt, and the Jimeng link flow

**Files:** Create `scripts/media_probe.py`, `scripts/jimeng_link.py`, `tests/test_media_probe.py`, `tests/test_link_flow.py`.

- [ ] Write failing tests for codec, dimensions, fps, duration, size, SHA-256, partial files, and a missing ffprobe.
- [ ] Compose the vendored protocol validators (container, codec, frame range, file size) with a system-ffprobe probe for codec/dimensions/fps/duration, then hash the final bytes and reject a file that changed between probe and hash using pre/post stat checks.
- [ ] Assemble and validate the schema-complete `ArtifactReceipt` with `validate_document("artifact_receipt", payload)`.
- [ ] Reuse the vendored bridge and upload path to produce a Jimeng link; return the ready link and its resource payload.
- [ ] Prove a missing ffprobe yields `DEPENDENCY_MISSING` and never installs software.
- [ ] Commit with `feat: validate previews and produce Jimeng links`.

### Task 4: Codex Skills and recovery workflows

**Files:** Create `skills/codex-blender-use/SKILL.md`, `skills/codex-blender-inspect/SKILL.md`, `skills/codex-blender-export-preview/SKILL.md`, `skills/codex-blender-link/SKILL.md`, `tests/scenarios/*.md`.

- [ ] Run and save no-skill baselines for: missing Blender, untrusted embedded scripts, absent camera, output outside scope, render timeout, and a request to upload without authorization.
- [ ] Implement `codex-blender-use` as the router; it must not duplicate the capability Skills.
- [ ] Implement inspect, export, and link Skills one at a time, validating each before starting the next.
- [ ] Verify the router refuses to upload without explicit authorization and never retries a render.
- [ ] Commit with `feat: add Codex Blender workflows`.

### Task 5: Distribution and verification gates

**Files:** Modify `scripts/validate_distribution.py`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`; create `tests/test_distribution.py`, `docs/verification/offline.md`, `docs/verification/blender-runtime.md`.

- [ ] Extend the validator and its tests for: repository URL `https://github.com/partme-ai/codex-blender-plugin.git`, plugin ID, version, the four-Skill inventory, provenance/license metadata, no committed binaries above a size threshold, no symlinks, and secret patterns.
- [ ] Assert `vendor/jimeng_blender_uploader/UPSTREAM.md` exists and records the five hashes, so a distributed build can be audited.
- [ ] Run the full offline suite, plugin validation, the link checker, a secret scan, and `git diff --check`.
- [ ] Record offline evidence without upgrading it to runtime evidence.
- [ ] Runtime acceptance: if an authorized Blender executable is available, run one fixture scene and record the exact version; otherwise record `runtimeAcceptance=BLOCKED_MISSING_AUTHORIZED_RUNTIME`.
- [ ] Commit with `test: verify Codex Blender distribution`.

---

## Completion gate

```text
vendored_core_tests = PASS
export_tests = PASS
restoration_tests = PASS
media_tests = PASS
link_flow_tests = PASS
skill_quick_validation = 4/4
plugin_validation = PASS
provenance_recorded = PASS (5/5 upstream hashes)
bundled_binaries = 0
secret_matches = 0
runtime_acceptance = PASS or explicitly BLOCKED
```
