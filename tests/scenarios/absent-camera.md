# Scenario: Absent Camera

## Context
User requests a camera render but the scene has no camera, or the named camera doesn't exist.

## Expected Behaviour
- **No cameras in scene:** Inspection returns `NO_CAMeras` warning; export raises `CAMERA_NOT_FOUND`
- **Named camera missing:** Export raises `CAMERA_NOT_FOUND`
- Reports the error clearly; does NOT retry

## Skill Path
`codex-blender-inspect` → `NO_CAMERAS` warning
`codex-blender-export-preview` → `CAMERA_NOT_FOUND` error

## Test
```python
# Scene with no camera objects → inspect_scene() returns warnings=["NO_CAMERAS"]
# export_preview(camera="NonExistent") → raises BlenderError("CAMERA_NOT_FOUND")
```
