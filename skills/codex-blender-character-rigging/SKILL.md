---
name: codex-blender-character-rigging
description: Build and inspect editable Blender armatures, skin weights, IK controls, pole targets, joint limits, and prop constraints for character work.
---

# Character rigging

Establish scene scale and character height before creating bones. Build a named hierarchy with positive bone lengths and deform flags, then bind one intended body mesh and assign explicit, topology-bound weights. Inspect bound meshes and bone lengths after binding.

Use IK targets and pole controls for limbs that need planted or directed endpoints; keep FK available through the underlying pose bones. Add joint limits only where their axes and ranges are understood. Test that moving a hand or foot controller changes the intended chain without moving unrelated controls.

For props, keep one object and use an explicit constraint whose influence can be animated. Check world-space continuity at every ownership switch. Rebuild or rescale from recipe parameters when height changes; do not fake a rig by keyframing disconnected body-part objects. Current automatic weight painting and production deformation cleanup are not claimed—use explicit groups and inspect the result.

`rig.rigify_status` may inspect an already installed Rigify extension. Call `rig.rigify_generate`
only when that status reports the operator available and the selected armature is a compatible
metarig. Never install or enable Rigify implicitly.
