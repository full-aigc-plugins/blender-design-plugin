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

Downstream AI rendering platforms are outside this plugin's responsibility.
