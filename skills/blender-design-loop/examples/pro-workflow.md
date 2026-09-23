# Example — Pro workflow (high-quota subscription)

End-to-end worked example for the **Pro** mode of
`blender-design-loop`. Assumes the user is on a ChatGPT-Pro-equivalent
subscription, can afford subagent judge calls per round, and wants
more rigorous critique than Plus mode.

## Setup

```text
Project root: ~/projects/dream-courtyard
Working dir:  ~/projects/dream-courtyard
Target image: generated via image-factory-use (Codex CLI)
Tier:         Pro
Round budget: unbounded (driven by exit criteria + user time budget)
Time budget:  60 minutes
```

## Round 1

```text
1. Create .blender-loop/ in working dir. Add to .gitignore.
2. Dream step:
     - send image-factory-use with brief → image-factory-run
     - target.png written to .blender-loop/target.png
     - sha256: <recorded>
3. Launch harness:
     mkdir -p .blender-loop/renders
     python3 scripts/launch_harness.py \
       --session-id courtyard-loop-001 \
       --output-root "$(pwd)/.blender-loop/renders" \
       --execution-mode auto_with_budget
4. Orchestrator (this session) builds a baseline scene directly:
     - empty ground plane
     - 4 walls + tile roof
     - camera at low angle
     - single sun lamp
5. scene.screenshot into .blender-loop/round-1.png.
6. Judge subagent (fresh context, Pro mode):
     - paths: target.png, round-1.png
     - prompt: see references/rubric.md
     - returns: composition 2.0, lighting 1.5, materials 2.0,
                details 0.5, total 6.0
     - gap_list:
       "round-1 courtyard reads as too small relative to target"
       "tile material is uniform grey; target has varied red-tan"
       "shadows under eaves are too sharp; target has softer penumbra"
       "no plants; target has ivy on east wall"
       "camera position too high; target reads as eye-level"
7. State.json updated; orchestrator decides CONTINUE.
```

## Round 2

```text
1. Orchestrator hands gap_list to a fresh worker subagent:
     - "fix the gaps above. 5 gaps. Materials priority #1."
2. Worker: scales courtyard by 1.4x, lowers camera, varies tile
   material with noise-driven color shift, enables ray-traced
   soft shadows, places ivy procedurally along east wall.
3. scene.screenshot into .blender-loop/round-2.png.
4. Judge subagent (fresh context, sees target + round-1 + round-2 +
   round-1 verdict):
     - composition 2.5, lighting 2.0, materials 2.5, details 0.6,
       total 7.6
     - gap_list:
       "ivy color reads uniform dark green; target has sun-bleached
        highlights"
       "courtyard floor in target has wear patterns near entrance;
        current is uniform"
       "shadows are softer now but the lamp is still too cool; target
        has warm light"
5. CONTINUE.
```

## Round 3

```text
1. Worker: warmer sun lamp, ivy material with sun-bleach layer,
   procedural wear pattern on floor near entrance.
2. scene.screenshot into .blender-loop/round-3.png.
3. Judge: composition 2.7, lighting 2.6, materials 2.7, details
   0.7, total 8.7.
4. EXIT_PASS at score 8.7. Show user.
```

## Round 4 (FPS optimization after user said "looks great, can
you get it to 60fps?")

```text
1. Profile: particle count on ivy (now 8000) is the bottleneck.
2. Worker: reduce to 3000, drop material roughness texture to 1k
   resolution, switch from Cycles to Eevee (target looks fine with
   rasterization).
3. Re-render. score 8.5 (slight regression on materials — acceptable).
   FPS: 62 (was 38).
4. Present trade-off to user.
5. EXIT_PASS_FPS_OK.
```

## What the user sees

- 4 round PNGs + 1 target PNG, all with sha256 receipts in
  state.json.
- A per-round verdict with score breakdown + gap_list.
- A "trade-off explained" block when exiting on FPS optimization.
- The full state.json is on disk; user can resume iteration any
  time by re-running this skill with the same target.

## What makes Pro different from Plus

- Judge subagent is **fresh per round**, not the orchestrator.
  This is the most expensive single step in Pro mode but produces
  less-biased scores.
- No mandatory 3-round checkpoint — the loop exits when criteria
  are met or user calls it.
- The orchestrator may build directly (no subagent) when it has
  higher confidence than a fresh-context worker.
- Stall detection is more aggressive in Pro: a 2-round no-improvement
  forces a dramatic redesign round before another judge call.

## When to switch back to Plus mid-session

If the user runs out of subagent quota, the orchestrator can
**degrade** mid-session from Pro to Plus: stop spawning judge
subagents, do self-inspection instead, and add the mandatory
3-round checkpoint back in. Record the switch in state.json so
the user understands the verdict quality dropped.