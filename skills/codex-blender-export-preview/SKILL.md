---
name: codex-blender-export-preview
description: "Export a reversible preview video from a Blender scene using the vendored Jimeng render core. Supports white_model, material_preview, and existing_video modes. Verified scene restoration on every exit path."
---

# Codex Blender Export Preview — Reversible Preview Export

Export a preview video from a Blender scene. The actual rendering is delegated to the vendored `jimeng_blender_uploader` render core; this skill wraps it with verified scene restoration.

## When to Use

- As part of the camera-render flow (after inspection, before link production)
- When the user says "render my scene" or "export preview"

## Interface

```
export_preview(bpy_module, request: dict) -> dict
```

**Args:**
- `bpy_module`: The `bpy` module (or a fake for testing)
- `request`: Dict with keys:
  - `projectPath`: str (path to the `.blend` file)
  - `mode`: `"white_model"` | `"material_preview"` | `"existing_video"`
  - `outputDir`: str (approved output directory)
  - `camera`: str (camera object name)
  - `frameStart`: int
  - `frameEnd`: int
  - `resolution`: str (`"origin"`, `"360p"`, `"480p"`, `"720p"`, `"1080p"`)

**Returns:** Dict with keys:
- `artifactPath`: str (absolute path to the MP4)
- `previewMode`: str
- `camera`: str
- `frameRange`: `{"start": int, "end": int}`
- `restoration`: `{"status": "confirmed"|"failed"|"unknown", "mismatches": [], "warnings": []}`
- `bytes`: int

**Note:** This is a PARTIAL `ArtifactReceipt`. Task 3 adds the probe-derived fields (`codec`, `width`, `height`, `fps`, `durationSeconds`, `sha256`).

## Preview Modes

| Mode | Behaviour |
|---|---|
| `white_model` | Workbench render with single-colour shading |
| `material_preview` | Workbench render preserving user materials |
| `existing_video` | No scene mutation; returns the approved local file |

## Restoration Guarantee

The adapter owns an **outer snapshot / verify / repair** pass:

1. Snapshot all scene fields BEFORE calling the vendored core
2. Call the vendored `render_preview_movie()`
3. Verify the scene state matches the snapshot
4. If the vendored core failed to restore any field, repair it
5. Report `restoration.status` by **outcome**:
   - `confirmed`: final state equals snapshot
   - `failed`: still differs after repair
   - `unknown`: no comparison possible

**Never report `confirmed` merely because a `finally` ran.** The status is verified, not assumed.

## Failure Categories

| Category | Condition |
|---|---|
| `CAMERA_NOT_FOUND` | No camera with the given name exists |
| `RENDER_FAILED` | Render or encode failed |
| `PROJECT_NOT_AUTHORIZED` | Symlink or path escape detected |
| `DEPENDENCY_MISSING` | ffmpeg not found |
| `INVALID_FRAME_RANGE` | Frame range validation failed |

## Safety Rules

- One attempt per call — never retry a render or encode
- Frame directory cleaned on every exit path (including render failure)
- Output containment: artifact must resolve inside the approved output directory
- Auto-execution stays disabled
- `existing_video` must NOT open or mutate the scene

## Maya

Out of scope. This integration is Blender-only.

## Files

- `scripts/blender_bridge.py` — `export_preview()`, `restored_scene_state()`
- `vendor/jimeng_blender_uploader/viewport_render.py` — vendored render core
- `tests/test_preview_export.py` — export tests
