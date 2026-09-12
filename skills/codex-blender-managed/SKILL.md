---
name: codex-blender-managed
description: "Start a non-invasive Blender design session from Codex without installing a Blender Add-on. Use for new projects or when the user wants Codex to launch Blender."
---

# Managed Blender Session

Discover Blender and launch `scripts/managed_bootstrap.py` in foreground mode with
`--disable-autoexec`. Do not change Blender preferences. A project path must be an authorized
regular `.blend`; omit it for a new design.

Wait for the private `0600` session descriptor, then communicate through `harness_cli.py`.
Keep Blender alive until the user closes it or authorizes `session.close`. Never fall back to
unreviewed arbitrary Python when the Harness fails to start.
