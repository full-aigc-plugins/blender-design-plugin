# Scenario: Output Outside Scope

## Context
The requested output directory is a symlink, or is not an existing directory, or the artifact
resolves outside the approved directory.

## Expected Behaviour
- **Symlinked output directory:** rejected as a request error; the add-on is never invoked
- **Non-existent output directory:** rejected as a request error
- The approved directory is passed to the add-on **resolved**, so a symlinked scope cannot be
  smuggled past the check

## Why this is ours, not the add-on's
The add-on writes wherever `scene.jimeng_output_dir` points and performs no containment check.
Scope validation is therefore caller-side request validation — it is not a reimplementation of
any add-on rule.

## Skill Path
`codex-blender-export-preview` → `_validate_output_dir` → request error

## Test
```python
# run_flow(..., {"outputDir": <symlink>}) raises ValueError mentioning "symlink"
# run_flow(..., {"outputDir": "/nonexistent"}) raises ValueError
# scene.jimeng_output_dir is set to the resolved path
```
