# Rubric Reference — 4-dimension visual scoring

Sourced from `research/dream-loop/references/pro-mode/workflow.md`.
This file is the **exact language** the judge subagent should be
given in Pro mode. Do not paraphrase — the consistency of the
rubric across rounds is what makes the trajectory meaningful.

## The rubric

Score along this rubric:

| Dimension | Max | What to check |
|---|---|---|
| **Composition** | 3 | Are the camera, framing, and layout correct? Are the position and scale of all major components correct compared to the target image? |
| **Lighting** | 3 | Color palette, exposure, shadows, contrast, atmosphere. Pay attention to reflections, glows. Ensure the scene overall is not too dark or too light compared to the target. |
| **Materials** | 3 | Every surface looks right — expected textures, roughness, translucency, wetness. Assets don't look blocky, plasticky, smooth, or fake unless the target image specifically does this. |
| **Details** | 1 | Fine-tooth comb. Not a single pixel should be different. Every tiny speck and detail should match between the two images. |

**Total: 10.** Fractional scores are allowed (e.g. 2.5 for half-correct
lighting). Be precise.

## The judge prompt (Pro mode)

Pass this exact prompt to the fresh-context judge subagent. Replace
the paths with the actual round-N and target paths.

> You are judging how close the current Blender scene is relative to
> the target image. Score along this rubric:
>
> - **Composition (0-3):** Are the camera, framing, and layout
>   correct? Are the position and scale of all major components
>   correct compared to the target image?
> - **Lighting (0-3):** Check color palette, exposure, shadows,
>   contrast, and atmosphere. Pay attention to reflections, glows,
>   etc. Ensure the scene overall is not too dark or too light
>   compared to the target.
> - **Materials (0-3):** Check that every surface looks right, with
>   the expected textures, roughness, translucency, wetness, etc.
>   Ensure assets don't look blocky, plasticky, smooth, or fake,
>   unless the target image specifically also does this.
> - **Details (0-1):** Go through everything with a fine-toothed
>   comb. Not a single pixel should be different. Every tiny speck
>   and detail should match between the two images.
>
> You can give fractional scores. You should be nitpicky and precise,
> and include a list of all gaps and blockers that need to be resolved
> for a perfect score on each category. It's OK to output a gigantic
> list if the current product is nowhere close to the target. It
> needs to be comprehensive and actionable so that another agent
> could go fix everything on the list, come back, and get a
> substantially improved score. Avoid non-actionable feedback like
> "This tree looks fake." You need to name exactly what's giving
> that impression and how the agent should fix it.
> Everything is within reason. If models or scenes need to be
> completely redesigned, say so. Don't sugarcoat it. The goal is for
> both images to be identical. The product should exactly reach the
> target. Do not settle for less.
>
> You should lastly also provide a total score out of 10 by summing
> these up.
>
> If a previous verdict and screenshot are provided, maintain
> consistency with prior judgment, but do not feel obligated to
> match or increase score. If the product regressed, it should
> score worse.

## Parse the verdict

The judge should return a JSON-like structure. The orchestrator
parses into:

```json
{
  "composition": 2.5,
  "lighting": 1.5,
  "materials": 2.0,
  "details": 0.5,
  "total": 6.5,
  "gap_list": [
    "key light comes from the wrong side (rim looks cyan when target has warm rim)",
    "stone material on arch reads as plastic — increase roughness to 0.85 and add a small normal-map texture",
    "ground plane is uniform green; target has scattered leaves and pebbles"
  ]
}
```

The orchestrator should reject any verdict that doesn't include
both scores (numbers) and gap_list (≥ 1 string). "looks great" with
no gap list is a rubric-drift failure — re-prompt the judge with
the same prompt and require actionable output.

## What the judge should NOT do

- Score 8+ on the first round for any non-trivial scene. If the
  judge does, the rubric has drifted — re-read it.
- Use non-actionable language: "looks off", "not great", "the vibe
  is wrong". Always name the specific pixel/material/light issue.
- Compare the scene to anything other than the target image. Do
  not invoke "general taste".
- Modify the scene or suggest build steps; the judge is read-only.

## When the rubric doesn't fit (Plus mode)

In Plus mode, the orchestrator is also the judge. Apply the same
rubric yourself; do not soften it because you're cheaper. Be
nitpicky. The Plus budget savings come from **not spawning a
subagent**, not from **lower standards**.

## When the scene needs a different rubric

If the target is animated (video frames, motion reference), the
static rubric above is incomplete. **Stop and ask the user** whether
to:

- Score each frame separately (multi-target loop)
- Switch to a motion-only rubric (timing, easing, coherence)

Do not invent a motion rubric on your own; the user may have a
specific quality bar in mind.