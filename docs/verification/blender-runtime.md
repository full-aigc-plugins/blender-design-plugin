# Runtime Verification

**Status:** `BLOCKED_MISSING_AUTHORIZED_RUNTIME`

## What's Needed

A real Blender smoke test requires:
1. An explicitly authorized Blender executable (user must provide the path)
2. A fixture `.blend` scene with at least one camera
3. Network isolation (no remote calls during the test)
4. Pre/post scene state comparison

## What the Test Would Do

1. Open the fixture scene in Blender (background mode)
2. Run inspection → verify SceneReceipt
3. Run export → verify MP4 exists, non-zero bytes, correct codec/dimensions
4. Verify scene state matches pre-export snapshot
5. Record the exact Blender version

## Current State

- Blender is not installed on this host
- `command -v blender` returns empty
- The plan permits `runtimeAcceptance=BLOCKED_MISSING_AUTHORIZED_RUNTIME`
- All offline tests pass (145/145)

## To Unblock

Provide an authorized Blender executable path and a fixture scene, then run:

```bash
blender --background fixture.blend --python scripts/blender_bridge.py -- '{"projectPath":"fixture.blend","mode":"inspect"}'
```
