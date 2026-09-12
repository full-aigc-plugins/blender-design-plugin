# Scenario: Untrusted Embedded Scripts

## Context
User opens a `.blend` file that contains embedded Python scripts.

## Expected Behaviour
- Inspection proceeds without executing embedded scripts
- Auto-execution stays disabled
- Scene receipt is returned with any relevant warnings
- Embedded scripts are NOT executed

## Skill Path
`codex-blender-inspect` → read-only inspection → receipt

## Test
```python
# bpy.context.preferences.filepaths.use_scripts_auto_execute == False
# inspect_scene() does not call bpy.ops.script.execute()
# Receipt includes warnings if scripts are detected
```
