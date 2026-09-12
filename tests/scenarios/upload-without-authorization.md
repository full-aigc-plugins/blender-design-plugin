# Scenario: Upload Without Authorization

## Context
User requests a Jimeng link but hasn't explicitly authorized the upload.

## Expected Behaviour
- Router requires explicit user confirmation before producing a link
- Without confirmation, the router does NOT call `produce_jimeng_link()`
- Reports: "Please confirm you want to upload this video to Jimeng."
- Does NOT proceed until user confirms

## Skill Path
`codex-blender-use` → authorization gate → waits for confirmation

## Test
```python
# Router does not call produce_jimeng_link() without user confirmation
# Router prompts user for authorization
```
