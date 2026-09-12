---
name: codex-blender-inspect
description: "Inspect a Blender scene: cameras, frame range, resolution, materials, and warnings. Returns a structured SceneReceipt. Read-only — no scene mutation."
---

# Codex Blender Inspect — Scene Inspection

Inspect a loaded Blender scene and return a structured `SceneReceipt`. This is a read-only operation — it does not mutate selection, mode, active objects, or any datablock.

## When to Use

- Before exporting a preview (to discover cameras, frame range, resolution)
- When the user asks "what's in my scene?"
- As the first step of the camera-render flow

## Interface

```
inspect_scene(bpy_module, approved_project: Path) -> dict
```

**Args:**
- `bpy_module`: The `bpy` module (or a fake for testing)
- `approved_project`: Path to the `.blend` file for fingerprinting

**Returns:** A dict conforming to `schemas/scene_receipt.schema.json`

## Receipt Fields

| Field | Type | Description |
|---|---|---|
| `schemaVersion` | string | Always `"codex-blender.receipt/v1"` |
| `producer` | object | `{"name": "codex-blender", "version": "0.1.0"}` |
| `blenderVersion` | string | Blender version string |
| `projectFingerprint` | string | SHA-256 of the project file content |
| `cameras` | string[] | Sorted list of camera object names |
| `frameRange` | object | `{"start": int, "end": int}` |
| `resolution` | object | `{"width": int, "height": int}` (percentage-scaled) |
| `previewModes` | string[] | Available modes: `white_model`, `material_preview`, `textured` |
| `warnings` | string[] | Sorted warnings: `NO_CAMERAS`, `INVALID_FRAME_RANGE`, `UNSUPPORTED_NODES`, `LINKED_ASSETS_OUTSIDE_SCOPE` |

## Security

- Read-only: no scene mutation
- Project path validated: rejects symlinks, requires resolved path to be a file
- Output: exactly one JSON receipt on stdout, diagnostics on stderr
- Redacted: never prints project contents, full paths, or environment

## Maya

Out of scope. This integration is Blender-only.

## Files

- `scripts/blender_bridge.py` — `inspect_scene()` function
- `schemas/scene_receipt.schema.json` — receipt schema
