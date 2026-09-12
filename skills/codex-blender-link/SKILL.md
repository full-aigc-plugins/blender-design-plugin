---
name: codex-blender-link
description: "Produce a ready-to-open Jimeng link for a validated preview video. Reuses the vendored upload_bridge's local HTTP bridge."
---

# Codex Blender Link — Jimeng Link Production

Produce a ready-to-open Jimeng link for a validated preview video. The link uses the vendored `upload_bridge`'s local HTTP bridge to serve the video to the Jimeng web app.

## When to Use

- After exporting a preview (camera-render flow)
- When the user has a local video and wants to upload it (local-upload flow)
- As the final step before returning a link to the user

## Interface

```
produce_jimeng_link(video_path, prompt=None, target_url=None) -> dict
```

**Args:**
- `video_path`: Path to the validated MP4 file
- `prompt`: Optional prompt text (uses default `"A cinematic high quality video"` if empty)
- `target_url`: Optional target URL override (uses Jimeng default if empty)

**Returns:** Dict with keys:
- `redirect_url`: str — the URL to open in the browser
- `resource_info_url`: str — the local bridge's resource endpoint
- `port`: int — the local server port
- `video`: str — the resolved video path
- `prompt`: str — the prompt text used

## How It Works

1. Validate the video file (exists, non-empty, not a symlink)
2. Start a local HTTP bridge on `127.0.0.1` (ephemeral port)
3. The bridge serves the video file and a `resource_info` endpoint
4. Construct the redirect URL with `channel=blender` and the resource URL
5. Return the link info

The bridge lives for 30 minutes (configurable via `JIMENG_LOCAL_BRIDGE_TTL_MS`) and shuts down 60 seconds after the first download.

## Known Limitation (v0.1.0)

The vendored `upload_bridge.run_ffmpeg` sets `cwd` to the upstream helper directory, which was excluded from the vendor. This means non-MP4 files (`.mov`, `.webm`, `.avi`) cannot be converted through the vendored path. **In v0.1.0, the local-upload flow accepts `.mp4` files only.** This will be resolved by either restricting the input or patching the vendored code with a documented deviation in `UPSTREAM.md`.

## Safety Rules

- **Never upload without explicit authorization.** The user must confirm before the link is produced.
- **Never retry.** One attempt per request.
- **Local only.** The bridge binds to `127.0.0.1` — no external access.

## Failure Categories

| Category | Condition |
|---|---|
| `RENDER_FAILED` | Video file missing, empty, or bridge failed |

## Maya

Out of scope. This integration is Blender-only.

## Files

- `scripts/jimeng_link.py` — `produce_jimeng_link()`
- `vendor/jimeng_blender_uploader/upload_bridge.py` — vendored bridge
- `tests/test_link_flow.py` — link flow tests
