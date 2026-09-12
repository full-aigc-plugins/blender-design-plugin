---
name: codex-blender-design
description: "Turn a user's idea into a Blender scene through milestone-based modeling, materials, lighting, camera, and animation commands."
---

# Blender Design Workflow

Inspect, translate the idea into named components, then complete Scene Structure, Modeling,
Materials, Lighting and Camera, Animation, and Final Preview milestones. Use one transaction per
milestone and `expectedSceneRevision` on every mutation.

Prefer registered commands over expert Python. After each milestone, generate fresh previews and
commit only after approval. On failure, recover the transaction. Command success alone is not
design acceptance. Downstream AI rendering is outside this Skill.
