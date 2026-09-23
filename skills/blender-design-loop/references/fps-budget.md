# FPS & Time Budget Discipline

Sourced from `research/dream-loop/SKILL.md` ("don't degrade for time
budget"). The principle:

> Don't degrade visual fidelity to hit the time budget. Don't take
> shortcuts. It's better to hit the time limit with meaningful,
> beautiful progress than with something roughly complete but ugly.

This is a **quality-over-completeness** stance. It applies to the
`blender-design-loop` skill specifically because the loop has both
a per-round budget (cost per round) and an overall budget (total
time the user is willing to wait).

## What this rule is NOT

It is **not** an excuse to:
- Skip the rubric. Score every round.
- Skip the critique step. Even short rounds get a verdict.
- Skip the screenshot. Even one-round loops must verify.
- Lower the ≥ 8 threshold because time is short.

## What it IS

It is permission to:
- Stop at score 6.5 if the scene is genuinely beautiful and the
  user said "60s budget, do something nice" — present the current
  state and ask.
- Stop at score 5.0 if the scene looks dramatically better than
  round 1 and the user said "low budget" — present, ask, do not
  silently degrade.
- Exit early on "stall approaching" with an unfinished scene —
  show the user, don't force a "completion" that destroys quality.

## What to record when budget exits early

Append to `.blender-loop/state.json`:

```json
{
  "exit_reason": "time_budget_exhausted",
  "final_score": 6.5,
  "best_round": 4,
  "user_choice_after_exit": null,
  "trade_off_explained": "Stopped at round 4 to honor the 60s budget. Best score 6.5 with material quality 'C+'. Could reach 8.0 with ~3 more rounds if budget is extended."
}
```

The `trade_off_explained` field is required — never exit silently.
The user must understand what they gave up.

## Optimization fallback (when score ≥ 8 but FPS unacceptable)

This is the ONLY case where the orchestrator continues work after
hitting the ≥ 8 threshold:

1. Profile which part of the scene is the bottleneck:
   - Reduce particle counts
   - Lower texture resolution
   - Decrease subdivision levels on geometry
   - Switch from Cycles to Eevee if photorealism allows
2. Re-render via `blender-harness`'s render commands.
3. Re-judge. **The score must not regress.** If it does, revert.
4. If score preserved but FPS still bad, ask the user whether to
   accept the trade or extend the budget.

## Related rules (in priority order)

1. **User rejection > model score > model score regression**. If
   the user looks at the screenshot and says "no, this is wrong",
   stop, even if the judge gave 8.5. The model is signal, not
   verdict.
2. **Stall detection > time budget**. If stall fires, do not
   push past it; show the user. They may want to abandon or pivot.
3. **Visual quality > completeness**. The dream-loop rule
   summarized.