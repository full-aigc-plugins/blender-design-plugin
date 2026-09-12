# Scenario: Render Timeout

## Context
The Blender render process hangs or takes too long.

## Expected Behaviour
- The vendored render core has a 900-second ffmpeg timeout
- If the render itself hangs, the adapter's outer restoration still runs
- Scene is restored even on timeout
- Reports `TIMEOUT` or `RENDER_FAILED`
- Does NOT retry

## Skill Path
`codex-blender-export-preview` → render timeout → restoration → error

## Test
```python
# Mock render to raise TimeoutExpired
# Verify scene is restored after timeout
# Verify error is reported, not retried
```
