# Scenario: Missing Blender

## Context
User requests a camera render but Blender is not installed.

## Expected Behaviour
- Router detects `BLENDER_NOT_FOUND`
- Reports: "Blender is not installed. Please install Blender and provide the executable path."
- Does NOT retry
- Does NOT download or install Blender

## Skill Path
`codex-blender-use` → detects missing Blender → error

## Test
```python
# blender_runner.discover_blender() raises BlenderNotFoundError
# Router catches and reports, does not retry
```
