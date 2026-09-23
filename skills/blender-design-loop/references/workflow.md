# Workflow Reference — dream-loop for Blender

Detailed iteration rules for the `blender-design-loop` skill. The
SKILL.md covers the high-level loop; this file covers what to do
when a specific situation arises.

## Per-round sequence (Pro mode)

```text
1.  Read state.json (or write a fresh one if round 1).
2.  Capture the current scene with scene.screenshot into
    .blender-loop/round-N.png. Overwrite flag is true by default.
3.  Spawn a fresh-context judge subagent with:
      - path to target.png
      - path to round-N.png
      - path to round-(N-1).png and last verdict (if N > 1)
      - references/rubric.md content
      - one-line instruction: "Score along the rubric. Be nitpicky
        and concrete. Name every gap."
4.  Parse the verdict into:
      scores    = {composition, lighting, materials, details, total}
      gap_list  = [str, str, ...]  # ordered, most-actionable first
5.  Compare to prior round's verdict (if any).
6.  Apply exit criteria (see SKILL.md).
7.  If continuing: build step.
8.  Write state.json with the new verdict + round counter.
9.  N += 1, loop.
```

## Per-round sequence (Plus mode)

The same as Pro, **except** step 3 is replaced by orchestrator
self-inspection:

```text
3'. Orchestrator opens both PNGs side-by-side (it has its own
    vision). Writes gap_list directly. Decides what the worker
    will change.
```

Plus mode saves the judge subagent call (which is the most expensive
single step in Pro) but pays for it in less-rigorous critique.

## Stall detection

"Stall approaching" triggers when **either**:

- The same gap appears in the judge's gap_list for 2 consecutive
  rounds. Example: "key light comes from wrong side" in round 3
  AND round 4 — that gap is not getting fixed by what you're doing.
- The best total score over the last 2 rounds did not improve by
  ≥ 1.0 point. (If round 3 = 6.4 and round 4 = 6.5, that counts
  as no improvement.)

When stall approaching fires:

1. Stop making incremental changes (don't tweak the lights by 5%).
2. Aim for a dramatic change: redesign the asset entirely,
   reposition the camera, rework the lighting setup, or swap the
   rendering engine (EEVEE ↔ Cycles).
3. Do NOT change the target image. The target is the contract.
4. Re-judge after the dramatic change.

"Stalled" triggers when a dramatic change after "stall approaching"
does not improve the score (or regresses). When stalled, stop the
loop and ask the user.

## Score trajectory vs time budget

Score is not strictly monotonically increasing — judge subagents
maintain consistency but a redesign round may dip and rebound.
Trust the trajectory over 2-3 rounds, not the single latest score.

If the time budget expires with the scene in a high-scoring state
but not at the ≥ 8 threshold, **show the user the screenshot and
ask** whether to keep iterating or accept. Do not silently lower
the threshold.

## When to refuse iteration entirely

- The target image depicts a real-world location/photograph and
  the user is asking for an "exact match" — Blender cannot do
  photorealistic matches in this loop without expensive setup.
- The user wants a different engine (Unreal / Cinema 4D) — out
  of scope.
- The user's scene file is read-only / shared with a teammate —
  warn them that iteration will create a new scene state every
  round and they should make a backup first.
- The user has no image-gen access (Plus mode with no Codex image
  capability, no baoyu key, no Dreamina account). Stop and explain.

## Workspace discipline reminders

- `.blender-loop/` is per-project; if the user has multiple Blender
  projects open, isolate loops per project directory.
- Never reuse round numbers across attempts (round-1.png, round-2.png).
  Always write `round-N.png` where N is the current round.
- After every round, write `state.json` with:
  ```json
  {
    "round": N,
    "target_path": ".blender-loop/target.png",
    "live_path":   ".blender-loop/round-N.png",
    "scores":      {"composition": C, "lighting": L, "materials": M, "details": D, "total": T},
    "gap_list":    ["...", "..."],
    "next_action": "build" | "exit_pass" | "exit_stall" | "exit_ask_user",
    "notes":       "..."
  }
  ```
  This makes it trivial to resume the loop if the orchestrator
  session is interrupted.

## Failure modes to watch for

- **Judge rates everything 8+**: rubric drift. Re-read the rubric;
  make the judge more concrete (e.g. "the rim light on the left
  shoulder reads as too cool").
- **Judge rates everything 2-3**: judge is being too harsh, or the
  dream step produced a target that does not match what the scene
  can render. Reconsider the target generation prompt.
- **Build step keeps reverting**: the worker subagent is fighting
  the harness's transaction model. Pass them an extra link to
  the `blender-harness` SKILL.md and have them re-read transaction
  discipline before the next round.
- **scene.screenshot returns MEDIA_INVALID**: render produced an
  empty file. Likely the scene has no camera or no objects. Inspect
  with `scene.inspect` before screenshotting.

## See also

- `rubric.md` — the 4-dimension scoring language
- `assets-3d.md` — port of dream-loop's fal.md recipes for Blender
  asset generation
- `fps-budget.md` — "don't degrade for time budget" discipline