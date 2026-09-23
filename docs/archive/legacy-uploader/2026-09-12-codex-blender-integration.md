# Codex Blender Integration Plan (Revision 3)

> **Status (2026-09-12):** Offline implementation complete; real Blender runtime acceptance
> remains `BLOCKED_MISSING_AUTHORIZED_RUNTIME`. The completion ledger at the end of this
> document is authoritative. The unchecked Revision 2 task lists are retained as historical
> TDD instructions and must not be interpreted as current implementation gaps.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the official `jimeng_blender_uploader` render/encode/upload engine drivable from Codex, headlessly, with verified restoration and a validated artifact receipt.

**Architecture:** Codex Skills invoke a safe Python runner and bridge. Inside a user-installed
Blender, `scripts/codex_bridge.py` registers the **complete, byte-identical** official add-on,
sets the same scene properties as its panel, and calls `bpy.ops.jimeng.render_upload()` or
`bpy.ops.jimeng.upload_existing()`. Protocol fetching, validation, rendering, encoding, error
taxonomy, restoration, and Jimeng link creation remain owned by the official operators. Codex
adds only request-scope validation, read-only inspection, process isolation, result projection,
and post-run restoration verification.

**Tech Stack:** Codex plugin manifest, Agent Skills, Python 3, Blender Python API, vendored third-party modules, JSON Schema, unittest, system ffmpeg/ffprobe.

**Supersedes:** Revision 2's five-module/headless-core adapter design as well as the original
clean-room rule. Commit `c5f1ca2` is the architectural correction: it removes the duplicated
`media_probe.py`, `jimeng_link.py`, and preview adapter and delegates both end-to-end flows to
the official operators. The contracts, distribution validator, safe runner, read-only scene
inspection, and restoration observation remain Codex-owned.

## Provenance facts (bind every task)

Upstream package: `jimeng_blender_uploader`, version **1.0.0**, macOS/CN build, obtained as
`jimeng_blender_uploader-mac-cn-1.0.0.zip`. The complete Python/UI package and legacy helper
directory are vendored byte-for-byte; only the bundled ffmpeg runtime is excluded. The full
13-file SHA-256 inventory is maintained in `vendor/jimeng_blender_uploader/UPSTREAM.md` and
asserted by `tests/test_vendored_core.py`. The five original core hashes remain:

```
dcc_config.py        d559a7d3202a0621bc986e3069f6069d3a2c400908377fc521b6a20f75663cc4
upload_bridge.py     714d34aa2426e8a2f2fba61cb3fca54cf4f60e6252e7e79079b4471c68593393
settings.py          69454485ff3db83acb05145899af166398a132927b96203565ff42f78b598db8
variant.py           3e6fa3b54953634ff44aa3df0f00774ab7279644d8b12c3d49d8c4e174c7fba3
viewport_render.py   b9f1e6fcecd1ca704262f407fb9854540b37f6aab28a2635f3f0c8567f5f252b
```

The official registration and operator path additionally requires upstream `__init__.py`,
`operators.py`, `panel.py`, and `state.py`. The helper directory is retained because ffmpeg is
launched with it as the working directory; its Node bridge is never executed by Codex.

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

**The two user-facing flows are the authority** (`docs/reference/upstream-user-manual.md`). The
official Blender panel offers 相机渲染 (camera render, then a Jimeng link) and 本地上传 (link an
already-rendered local video). The Skills must expose recognisably the same two flows, and the
router must send each user request to the right one.

- [ ] Run and save no-skill baselines for: missing Blender, untrusted embedded scripts, absent camera, output outside scope, render timeout, and a request to upload without authorization.
- [ ] Implement `codex-blender-use` as the router; it must not duplicate the capability Skills. It selects the camera-render flow or the local-upload flow from the user's intent, and never treats "here is a video file" as a render request.
- [ ] Implement inspect, export, and link Skills one at a time, validating each before starting the next.
- [ ] The camera-render flow ends in a Jimeng link; the local-upload flow must not open or mutate a Blender scene.
- [ ] Verify the router refuses to upload without explicit authorization and never retries a render.
- [ ] State in each Skill that Maya is out of scope for this repository.
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

## Revision 3 completion ledger (authoritative)

| Planned outcome | Status | Evidence |
| --- | --- | --- |
| Contracts, manifest, schemas, validator | Complete | `45da963`, `84b58d6`, contract/distribution tests |
| Safe Blender discovery and process runner | Complete | `99d9600`, `f148f93`, runner tests |
| Read-only scene inspection | Complete | `74c5568`, `421a152`, inspection tests |
| Official add-on provenance and byte parity | Complete | `4b996b3`, `c5f1ca2`, 13-file hash/parity tests |
| Camera-render Codex integration | Complete offline | `c5f1ca2`; delegation, input, error, and restoration-observation tests |
| Existing-video/Jimeng-link integration | Partial | Operator delegation/no-render tests pass, but the runner still requires and loads `projectPath` |
| Four Agent Skills and recovery scenarios | Complete | `88e1f4a`, revised by `c5f1ca2`; distribution frontmatter/inventory checks |
| Distribution and secret/binary/symlink gates | Complete | `00d0c7a`, `84b58d6`, `2fb2ce3`; distribution validator |
| Real Blender runtime smoke test | Blocked | No authorized Blender executable was found on this host |

The remaining local-upload integration task is to add a Blender factory-startup argv path and
allow `blender_bridge.main()` to dispatch `local_upload` without `projectPath`, while preserving
the existing project authorization rules for inspection and camera rendering. This behavior
change requires new RED tests before implementation.

Fresh verification on 2026-09-12: `python3 -m unittest discover -s tests -q` ran 163 tests
with zero failures; `python3 scripts/validate_distribution.py` and `git diff --check` exited
successfully. Expected tracebacks from injected official-operator failure tests are printed by
upstream code, so the suite is green but intentionally not silent.
