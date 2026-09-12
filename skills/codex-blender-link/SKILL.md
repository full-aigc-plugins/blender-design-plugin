---
name: codex-blender-link
description: "Produce a Jimeng link for a preview video, by driving the official add-on's own upload flow headlessly."
---

# Codex Blender Link — Local Upload Flow (本地上传) and Link Production

Produce a ready-to-open Jimeng link. Both the camera-render flow and the local-upload flow
produce their link *inside the add-on's own operator* — this Skill covers the local-upload
flow (choosing an existing video) and explains where the link comes from.

## When to Use

- The user already has a rendered video and wants a Jimeng link
- The user asks to "upload this video" or "link this file"

## What We Call

```
codex_bridge.run_flow(bpy_module, {"flow": "local_upload", "videoPath": ...})
    -> enables the vendored add-on via its register()
    -> sets scene.jimeng_uploader_mode = "EXISTING" and scene.jimeng_video_path
    -> calls bpy.ops.jimeng.upload_existing()
    -> projects the add-on's own scene state into the result
```

The operator we call is `JIMENG_OT_upload_existing` in
`vendor/jimeng_blender_uploader/operators.py`. It already performs, in order:

1. fetch + validate the DCC protocol config
2. validate the video path and standardize non-MP4 inputs via the vendored `upload_bridge`
3. start the local HTTP bridge, passing the protocol's file-size limit
4. set `jimeng_redirect_url` / `jimeng_link_ready` on the scene

**This flow never opens or mutates a Blender scene.** It reads one scene property, writes the
link back, and that is all — no render, no camera, no frame range.

**Do not reimplement any of that here.** See `vendor/jimeng_blender_uploader/UPSTREAM.md`.

## Result

`jimeng_redirect_url` is the link the add-on produced; `jimeng_link_ready` says whether it is
usable; `jimeng_error_message` carries the add-on's own message when it is not.

## The Local Bridge

The bridge is the vendored add-on's own: loopback-only, ephemeral port, token-guarded, serving
the video plus a resource-info payload the Jimeng page reads. It lives for 30 minutes
(`JIMENG_LOCAL_BRIDGE_TTL_MS`) and shuts down 60 seconds after the first download. We start it
only by calling the add-on's operator.

## Safety Rules

- **Never upload without explicit authorization.** The user must confirm before the flow runs.
- **Never retry.** One attempt per request.
- Local only: the bridge binds `127.0.0.1`; nothing is published.

## Maya

Out of scope. This integration is Blender-only.

## Files

- `scripts/codex_bridge.py` — the thin driver (`run_flow`)
- `vendor/jimeng_blender_uploader/operators.py` — `JIMENG_OT_upload_existing`
- `vendor/jimeng_blender_uploader/upload_bridge.py` — bridge + ffmpeg discovery
- `tests/test_codex_integration.py` — proves delegation and that no render happens
