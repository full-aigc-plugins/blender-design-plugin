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

Inspect before mutation and carry the returned scene revision. Use one transaction per milestone
and fresh camera/front/side/top previews before approval. Deletion, overwrite, final export,
expert Python, and session close require action-bound authorization.

## Input and delivery contract

When the user asks for an end-to-end automated design, offer or honor one
`auto_with_budget` envelope instead of requesting approval at every milestone:
approved output root, requested deliverables, missing-asset policy, optional
downstream budget, and permission for Blender-designed proxies. Complete all
safe milestones automatically, retain fresh evidence internally, and return a
single final artifact inventory. `interactive` remains available for users who
want stage review; `review_only` makes no mutation or export.

Before designing, turn the request into an implementation brief: scene purpose, required assets,
object count and constraints, scale, environment, camera plan, animation beats, duration, and
target deliverables. Identify every missing reference asset explicitly.

If a required asset is missing, ask the user to provide it by default. Only create a substitute
asset when the user explicitly asks Codex to design it; mark that asset as a Blender-designed
proxy rather than a supplied reference. Never silently invent a supplied reference's identity,
motion, appearance, or exact dimensions.

At completion, return a named artifact inventory with absolute paths, formats, checksums,
validation evidence, scene revision, and known deviations from the brief. Then ask the user to
choose either: finish with the local Blender delivery, or hand the validated artifacts to a
separately installed downstream-renderer workflow. Do not initiate that handoff, upload, login,
quote, submission, or paid operation without the user's separate instruction.

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
