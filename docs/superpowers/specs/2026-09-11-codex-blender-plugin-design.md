# Codex Blender Plugin Design

## Goal

Deliver an installable Codex plugin that safely inspects authorized Blender projects and exports validated local preview videos through reversible Blender automation.

## Required behavior

- Discover Blender without installing it.
- Inspect before mutation and return a structured scene receipt.
- Require explicit project and output scopes.
- Export white-model or material-preview video from a selected camera and frame range.
- Restore every temporary scene setting on success, failure, cancellation, and timeout.
- Validate the final media and emit an artifact receipt usable by `dreamina-3d`.

## Non-goals

No remote upload, paid generation, arbitrary add-on execution, vendor source reuse, bundled Blender, or bundled ffmpeg.

## Acceptance

All schema, path, fake-bpy, restoration, media, and plugin-package tests pass. A real Blender smoke test is a separate environment gate and cannot be inferred from unit tests.
