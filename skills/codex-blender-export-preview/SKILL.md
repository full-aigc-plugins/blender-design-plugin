---
name: codex-blender-export-preview
description: "Render a preview video from a Blender scene camera and produce a Jimeng link, by driving the official add-on's own render operator headlessly."
---

# Codex Blender Export Preview — Camera Render Flow (相机渲染)

Run the official Jimeng add-on's **camera render** flow headlessly. Our code does not render,
validate, or restore anything itself — it enables the vendored add-on, sets the same scene
inputs the Blender panel would set, invokes the add-on's operator, and reports back what the
add-on produced.

## When to Use

- The user wants a preview rendered from a Blender scene camera
- After a read-only inspection, so the camera and frame range are known

## What We Call

```
codex_bridge.run_flow(bpy_module, {"flow": "camera_render", ...})
    -> enables the vendored add-on via its register()
    -> sets scene.jimeng_uploader_mode / jimeng_camera / jimeng_resolution
       / jimeng_frame_start / jimeng_frame_end / jimeng_output_dir
    -> calls bpy.ops.jimeng.render_upload()
    -> projects the add-on's own scene state into the result
```

The operator we call is `JIMENG_OT_render_upload` in
`vendor/jimeng_blender_uploader/operators.py`. It already performs, in order:

1. fetch + validate the DCC protocol config
2. sync camera export parameters and derive the frame range
3. validate the frame range against the protocol
4. render the preview (`viewport_render.render_preview_movie`)
5. validate the output file size
6. start the local bridge and produce the Jimeng link
7. set the link on the scene and record the camera-keyed cache

**Do not reimplement any of that here.** If this Skill or our code appears to duplicate it,
that is a defect: delegate instead. See `vendor/jimeng_blender_uploader/UPSTREAM.md`.

## Request Fields

| Field | Meaning |
|---|---|
| `flow` | `"camera_render"` |
| `projectPath` | the `.blend` file (path-checked before anything else) |
| `camera` | camera object name (required; absence is a request error) |
| `resolution` | `origin`, `360p`, `480p`, `720p`, `1080p` |
| `frameStart`, `frameEnd` | frame range; the add-on validates/normalises it |
| `outputDir` | approved output directory |
| `prompt` | optional prompt text |

## Result

The result is a projection of the add-on's own state: `operatorResult`
(`FINISHED`/`CANCELLED`), `jimeng_task_state`, `jimeng_redirect_url`, `jimeng_video_path`,
`jimeng_error_message`, `jimeng_status`, and a `restoration` block produced by our
read-only verification (see below).

## Error Taxonomy

Errors are the add-on's, not ours. `jimeng_error_message` carries the add-on's own localized
message (for example its 44-frame minimum hint) and `jimeng_task_state` is `FAILED`. We do not
translate, re-categorise, or retry.

## Restoration

The add-on restores the scene settings it changes. Our contribution is **verification only**:
`blender_bridge.verify_restoration()` snapshots the fields the add-on's render path touches
before the call and compares afterwards, reporting `confirmed` or `failed` with the differing
fields. We deliberately do not restore on the add-on's behalf — that would duplicate its logic.

## Safety Rules

- One attempt per call; never retry a render
- Auto-execution stays disabled
- The project path is rejected if it is a symlink or does not resolve to a file
- No shell strings; argv arrays only

## Maya

Out of scope. This integration is Blender-only.

## Files

- `scripts/codex_bridge.py` — the thin driver (`run_flow`, `enable_addon`)
- `scripts/blender_bridge.py` — `verify_restoration()`, `snapshot_scene_state()`, inspection
- `vendor/jimeng_blender_uploader/operators.py` — `JIMENG_OT_render_upload` (the real flow)
- `tests/test_codex_integration.py` — proves delegation
