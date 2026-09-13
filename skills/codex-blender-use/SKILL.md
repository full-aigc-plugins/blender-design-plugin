---
name: codex-blender-use
description: "Route requests to managed or Connector Blender workflows when a user wants Codex to create, modify, review, save, or export a Blender design."
---

# Codex Blender Router

Use this as the entry point. Route new or Codex-launched sessions to `codex-blender-managed`,
already-open Blender windows to `codex-blender-connector`, design work to
`codex-blender-design`, read-only questions to `codex-blender-inspect`, visual evidence to
`codex-blender-preview`, approved outputs to `codex-blender-export`, and failures to
`codex-blender-recover`.

After the implementation brief, load only the required domain Skills:

- scene organization and approved imports → `codex-blender-scene-assembly`
- mesh/product work → `codex-blender-hard-surface`; curves → `codex-blender-curves`
- UV/material work → `codex-blender-uv-material`; procedural nodes → `codex-blender-procedural-modeling`
- rigs → `codex-blender-character-rigging`; animation → `codex-blender-character-animation`
- camera work → `codex-blender-cinematography`; acceptance measurements → `codex-blender-quality-validation`
- sculpt, hair, or simulation → `codex-blender-sculpt-surface`, `codex-blender-hair`, or `codex-blender-simulation`
- rendering/compositing → `codex-blender-render-compositing`
- Grease Pencil, tracking, or VSE → `codex-blender-grease-pencil`, `codex-blender-tracking`, or `codex-blender-sequence-editing`
- `job.*` → `codex-blender-background-jobs`; add render-compositing for EXPORT, RENDER_STILL, or RENDER_ANIMATION_FRAMES; add sequence-editing for COMPOSE_VIDEO; add simulation for BAKE_POINT_CACHES

For multi-domain or conditional requests, read the maintained [Skill routing reference](references/skill-routing.md).

Inspect before mutation and carry the returned scene revision. Use one transaction per milestone
and fresh camera/front/side/top evidence. Interactive mode waits for milestone review; automatic
mode evaluates the evidence and commits within the already approved task. Deletion, overwrite,
expert Python and external actions retain action-bound authorization. Automatic fresh-file
exports use the approved root, format scope and committed snapshot.

## Input and delivery contract

When the user asks for an end-to-end automated design, offer or honor one
`auto_with_budget` envelope instead of requesting approval at every milestone:
approved output root, requested deliverables, missing-asset policy, optional
downstream budget, and permission for Blender-designed proxies. Complete all
safe milestones automatically, retain fresh evidence internally, and return a
single final artifact inventory. `interactive` remains available for users who
want stage review; `review_only` makes no mutation or export.

Pass the selected mode into the actual launcher or Connector; a conversational promise is not
an active policy. Check `session.status.executionPolicy` before design. Show work in the
foreground window using the Codex panel and registered view/playback commands. Follow
[foreground control and recovery](references/foreground-policy.md) for command arguments,
takeover handling and limits. Respond to the user in their language, including Chinese.

Before designing, turn the request into an implementation brief: scene purpose, required assets,
object count and constraints, scale, environment, camera plan, animation beats, duration, and
target deliverables. Identify every missing reference asset explicitly.

Before promising a production method, query `capability.list` for its domain and follow
`nextOffset` until complete; use `capability.describe` with `{"id":"<registered command>"}`
to check arguments, prerequisites, availability, and evidence. L0 domains have no callable
implementation. L1 is only a basic interface; L2 adds a workflow; L3 requires real-project,
visual, and delivery validation; L4 adds recovery and compatibility. `unknown` availability
means prerequisites still need inspection, not that they passed. Report tool, Skill, and
real-project coverage separately. Expert Python does not fill a supported-domain claim.
If these catalog commands are absent in an older installed build, inspect the legacy
`session.capabilities` and state the evidence gap rather than inventing commands.

If a required asset is missing, ask the user to provide it by default. Only create a substitute
asset when the user explicitly asks Codex to design it; mark that asset as a Blender-designed
proxy rather than a supplied reference. Never silently invent a supplied reference's identity,
motion, appearance, or exact dimensions.

At completion, return a named artifact inventory with absolute paths, formats, checksums,
validation evidence, scene revision, and known deviations from the brief. If the user already
chose the delivery route, honor it without asking again. Otherwise ask whether to finish locally
or hand the validated artifacts to a separately installed downstream-renderer workflow. Export
alone does not authorize upload, login, quotation, submission or payment.

Downstream AI rendering platforms are outside this plugin's responsibility.

## Delivery routes

After the Blender artifact is ready, choose exactly one explicit route:

- `preview_only`: use `codex-blender-preview` or the receipt adapter and stop
  with a verified local file.
- `jimeng_web`: use `codex-blender-jimeng-web` against an already enabled
  official uploader in the foreground Connector session; stop at
  `JimengLinkReady`.
- `downstream_seedance`: hand the validated artifact inventory to the
  separately installed `codex-dreamina-3d` workflow. That workflow owns
  approval, paid submission, query-only recovery, and final download.

If intent is ambiguous, describe these three outcomes and ask the user to
choose. Never silently turn a preview export into a web handoff or a paid
generation.
