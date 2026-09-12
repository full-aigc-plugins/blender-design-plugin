# Codex Blender Plugin Technical Solution

> Historical clean-room proposal. Superseded on 2026-09-12 by
> `docs/superpowers/plans/2026-09-12-codex-blender-integration.md` Revision 3. The current
> solution vendors the complete official add-on and delegates both flows to its operators.

## 1. Decision

Use a thin Codex Skill layer plus a deterministic Python bridge launched by the user-installed Blender executable. Do not bundle Blender, ffmpeg, or vendor add-on code.

## 2. Proposed layout

```text
.codex-plugin/plugin.json
skills/codex-blender-*/SKILL.md
scripts/blender_runner.py
scripts/blender_bridge.py
scripts/media_probe.py
schemas/scene_receipt.schema.json
schemas/artifact_receipt.schema.json
tests/
```

## 3. Execution contract

The runner accepts JSON input on a file descriptor or temporary file and invokes Blender with an argv array. The bridge emits exactly one JSON receipt on stdout; diagnostics go to stderr with paths reduced to approved relative labels.

## 4. Preview modes

| Mode | Source | Output | Guardrail |
|---|---|---|---|
| white model | active scene/camera | Workbench MP4 | temporary material override, restored |
| material preview | user materials/textures | Workbench MP4 | unsupported nodes become warnings |
| existing video | approved local file | validated receipt | no scene mutation |

Resolution presets preserve aspect ratio; `origin` uses the current scene resolution. Numeric limits are configuration, not hard-coded vendor facts. A downstream profile may request the documented Dreamina limits, but this plugin only validates the supplied profile.

## 5. Testing strategy

- Pure Python tests for validation, state snapshots, path containment, and receipts.
- A fake `bpy` adapter for RED/GREEN behavior tests.
- Fixture `.blend` projects for camera, no-camera, materials, animation, and restoration.
- Optional real-Blender smoke tests gated by an explicit executable path.
- ffprobe-based media assertions when ffprobe is already available.

## 6. Failure model

Stable categories: `BLENDER_NOT_FOUND`, `UNSUPPORTED_VERSION`, `PROJECT_NOT_AUTHORIZED`, `CAMERA_NOT_FOUND`, `INVALID_FRAME_RANGE`, `RENDER_FAILED`, `TIMEOUT`, `RESTORE_UNCONFIRMED`, `MEDIA_INVALID`. No automatic retry is permitted for renders.

## 7. Clean-room rule

The official Seedance uploader was observed only to identify external behavior and interoperability constraints. Implementation must be written from these documents and tests without copying source, strings, identifiers, UI assets, or bundled binaries.
