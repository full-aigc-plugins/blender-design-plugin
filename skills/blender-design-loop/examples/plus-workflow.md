# Example — Plus workflow (low-quota subscription)

End-to-end worked example for the **Plus** mode of
`blender-design-loop`. Assumes the user is on a ChatGPT-Plus-equivalent
subscription and wants a 3D scene that matches a target image.

## Setup

```text
Project root: ~/projects/voxel-tavern
Working dir:  ~/projects/voxel-tavern
Target image: /Users/user/Downloads/tavern-target.png  (user-supplied)
Tier:         Plus
Round budget: 3 (Plus mode hard limit before mandatory checkpoint)
Time budget:  10 minutes
```

## Round 1

```text
1. Create .blender-loop/ in working dir. Add to .gitignore.
2. Copy target image to .blender-loop/target.png.
   (sha256 recorded in state.json)
3. Launch harness:
     mkdir -p .blender-loop/renders
     python3 scripts/launch_harness.py \
       --session-id tavern-loop-001 \
       --output-root "$(pwd)/.blender-loop/renders" \
       --execution-mode auto_with_budget
4. Worker subagent (fresh context, Plus mode):
     - path to target.png
     - "close the gap between current scene and target. Use only
        scene.inspect / mesh.* / material.* / light.* / camera.*
        / object.* via blender-harness. You are the worker; do
        not run blender-design-loop yourself."
   (Worker commits: creates ground plane, places hero prop, sets
    camera at target angle, applies ambient light.)
5. scene.screenshot into .blender-loop/round-1.png (1024×1024).
6. Orchestrator self-inspection (Plus mode — no judge subagent):
     - Composition: target has tavern centered, current scene has
       tavern off-center. Gap: "translate hero +2.5m on X".
     - Lighting: target has warm rim, current has flat. Gap:
       "add warm rim light from upper-right".
     - Materials: both blocks look okay (placeholders). No gap.
     - Details: target has lanterns, current doesn't. Gap:
       "add 6 hanging lanterns in front of door".
   Total: composition 1.5 / lighting 1.0 / materials 2.5 /
   details 0.5 = 5.5/10
7. State.json updated; orchestrator decides CONTINUE.
```

## Round 2

```text
1. Worker subagent (fresh context):
     - path to target.png
     - path to round-1.png
     - gap_list from round 1
     - "fix the gaps above. Do not introduce new gaps. Keep FPS
        above 30."
   Worker commits: re-positions hero, adds rim light, hangs 6
   lanterns procedurally.
2. scene.screenshot into .blender-loop/round-2.png.
3. Orchestrator self-inspection:
     - Composition: still slightly off-center. Gap: "nudge 0.5m".
     - Lighting: rim looks good. No gap.
     - Materials: lanterns look uniform plastic. Gap: "vary the
        lantern emissive intensity between 0.7 and 1.2".
     - Details: lanterns still don't cast shadow on ground. Gap:
        "enable shadows on lantern light objects".
   Total: 2.5 / 2.5 / 2.0 / 0.5 = 7.5/10
4. State.json updated; orchestrator decides CONTINUE.
```

## Round 3 (Plus mode mandatory checkpoint)

```text
1. Worker subagent:
     - path to target.png
     - path to round-2.png
     - gap_list from round 2
   Worker commits: lantern emissive variation + shadows enabled.
2. scene.screenshot into .blender-loop/round-3.png.
3. Orchestrator self-inspection:
     - Composition: very close to target now.
     - Lighting: matches.
     - Materials: lanterns now read correctly.
     - Details: most things aligned; small difference in door
        panel shading.
   Total: 2.8 / 2.8 / 2.5 / 0.8 = 8.9/10  →  EXIT_PASS
4. Present to user:
     "Round 3 hit score 8.9/10. Threshold reached. Latest screenshot:
     .blender-loop/round-3.png. Want me to keep iterating?"
```

## What the user sees

- 3 round PNGs + 1 target PNG, all with sha256 receipts in
  `state.json`.
- A single summary block with the gap_list per round and final
  score.
- Explicit "want me to keep iterating?" — Plus mode respects the
  user's budget by stopping at 3.

## What if the user says "yes, keep going"?

Reset the Plus counter to 0 and continue. The 3-round cap is per
checkpoint, not per session. Continue until exit criteria fire.

## What if the budget runs out before round 3?

Same discipline: present the latest screenshot, the latest verdict,
and what was lost to the budget. The user always decides.