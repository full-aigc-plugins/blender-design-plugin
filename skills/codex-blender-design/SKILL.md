---
name: codex-blender-design
description: "Turn a user's idea into a Blender scene through milestone-based modeling, materials, lighting, camera, and animation commands."
---

# Blender Design Workflow

Inspect, then create an implementation brief before mutation: requested assets, supplied
references, missing references, scene constraints, camera route, animation beats, duration, and
required exports. If a required reference is missing, ask the user for it by default. Create a
Blender-designed proxy only when the user explicitly requests design of the missing asset, and
record its assumptions and deviations in the delivery receipt.

For an `auto_with_budget` request, execute the approved brief through every safe milestone
without asking after each preview. Capture the same previews and validation evidence, but present
them together with the final artifact inventory. Stop only for a forbidden missing asset, path
escape, deletion/overwrite, expert Python, failed validation requiring recovery, or an exceeded
downstream budget.

Translate the approved brief into named components, then complete Scene Structure, Modeling,
Materials, Lighting and Camera, Animation, and Final Preview milestones. Use one transaction per
milestone and `expectedSceneRevision` on every mutation.

Prefer registered commands over expert Python. After each milestone, generate fresh previews and
commit only after approval. On failure, recover the transaction. Command success alone is not
design acceptance. Before final export, verify all brief constraints that are observable in the
scene and preview: object count and uniqueness, animation beat order, frame range, camera route,
and required deliverable formats. Return the artifact inventory and explicitly ask whether the
user wants to finish with the local delivery or request a separate downstream-renderer handoff.
Downstream AI rendering is outside this Skill.
