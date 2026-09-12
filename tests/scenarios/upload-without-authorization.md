# Scenario: Upload Without Authorization

## Context
The user asks for a Jimeng link but has not explicitly authorized the upload.

## Expected Behaviour
- The router requires explicit confirmation before running either flow
- Without confirmation the router does NOT call `codex_bridge.run_flow(...)`
- It reports that confirmation is needed and waits

## Skill Path
`codex-blender-use` → authorization gate → waits for confirmation

## Test
```python
# The router does not invoke run_flow() until the user confirms
# No bridge is started and no link is produced before confirmation
```
