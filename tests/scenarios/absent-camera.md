# Scenario: Absent Camera

## Context
The user requests a camera render but the scene has no camera, or the named camera is absent.

## Expected Behaviour
- **Named camera missing:** our driver raises a request error naming the camera; nothing is
  rendered and the add-on is not asked to run.
- **Scene has no cameras at all:** read-only inspection reports the `NO_CAMERAS` warning, so the
  user learns this before requesting a render.

## Skill Path
`codex-blender-inspect` → `NO_CAMERAS` warning
`codex-blender-export-preview` → request error naming the camera

## Test
```python
# run_flow(..., {"flow": "camera_render", "camera": "Nope"}) raises ValueError mentioning "Nope"
# inspect_scene() on a camera-less scene returns warnings=["NO_CAMERAS"]
```
