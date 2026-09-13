---
name: codex-blender-export
description: "Save or export an approved Blender design as BLEND, GLB, GLTF, FBX, OBJ, STL, PNG, JPG, or MP4 with verified receipts."
---

# Blender Export

Export only from the approved `sceneRevision + snapshotId` and under an approved output root.
Existing files require action-bound overwrite authorization.

Call `export.file`; verify existence, non-zero size, SHA-256, format, and receipt schema. Model
formats require isolated re-import validation; images and MP4 require media probing. Distinguish
local export success from any downstream rendering system.
