# Scenario: Output Outside Scope

## Context
User provides an output directory that is a symlink or resolves outside the approved scope.

## Expected Behaviour
- Export raises `PROJECT_NOT_AUTHORIZED`
- Reports: "output directory must not be a symlink" or "artifact escapes approved output directory"
- Does NOT write any file to the escaping location
- Scene is restored

## Skill Path
`codex-blender-export-preview` → containment check → `PROJECT_NOT_AUTHORIZED`

## Test
```python
# Symlink output dir → raises BlenderError("PROJECT_NOT_AUTHORIZED")
# Artifact that resolves outside output dir → raises BlenderError("PROJECT_NOT_AUTHORIZED")
```
