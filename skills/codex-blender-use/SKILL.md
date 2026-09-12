---
name: codex-blender-use
description: "Route Codex requests to the correct Blender workflow: camera render → Jimeng link, or local video upload → Jimeng link. This is the entry point for all codex-blender operations."
---

# Codex Blender Use — Router Skill

Route user intent to the correct Blender workflow. This skill is the entry point; it does NOT duplicate the capability skills — it selects one and delegates.

## Two User-Facing Flows

The official Jimeng Blender add-on offers two flows. This Codex integration exposes recognisably the same two:

### Flow 1: Camera Render (相机渲染)

**When:** The user wants to render a preview from a Blender scene camera.

**Route to:** `codex-blender-export-preview` → `codex-blender-link`

**Steps:**
1. Inspect the scene (`codex-blender-inspect`) to get cameras, frame range, resolution
2. Confirm the camera, frame range, and output directory with the user
3. Export the preview (`codex-blender-export-preview`)
4. Validate the artifact (media probe)
5. Produce the Jimeng link (`codex-blender-link`)
6. Return the link to the user

### Flow 2: Local Upload (本地上传)

**When:** The user already has a rendered video and wants to upload it to Jimeng.

**Route to:** `codex-blender-link` directly

**Steps:**
1. Validate the video file (exists, is a supported format, not a symlink)
2. Produce the Jimeng link (`codex-blender-link`)
3. Return the link to the user

**Important:** This flow must NOT open or mutate a Blender scene.

## Intent Detection

| User says | Route to |
|---|---|
| "render my scene" / "export preview" / "render from camera" | Flow 1 (camera render) |
| "upload this video" / "link my video" / "use this MP4" | Flow 2 (local upload) |
| "here is a video file" + a path | Flow 2 (local upload) — NOT a render request |
| Ambiguous | Ask the user to clarify |

## Safety Rules

- **Never retry a render.** One attempt per request.
- **Never upload without explicit authorization.** The user must confirm before the link is produced.
- **Never execute untrusted `.blend` scripts.** Auto-execution stays disabled.
- **Maya is out of scope.** This integration is Blender-only.

## Error Recovery

| Error | Recovery |
|---|---|
| `BLENDER_NOT_FOUND` | Tell the user to install Blender and provide the path |
| `CAMERA_NOT_FOUND` | Ask the user to select a valid camera |
| `INVALID_FRAME_RANGE` | Ask the user to fix the frame range |
| `RENDER_FAILED` | Report the error; do NOT retry |
| `DEPENDENCY_MISSING` | Tell the user to install ffmpeg/ffprobe |
| `PROJECT_NOT_AUTHORIZED` | Reject the path; ask for a valid one |

## Files

- `scripts/codex_bridge.py` — thin driver that enables the vendored add-on and calls its operators
- `scripts/blender_bridge.py` — read-only inspection + restoration verification
- `scripts/blender_runner.py` — launches Blender safely
- `vendor/jimeng_blender_uploader/` — the vendored official add-on (owns both flows)

Both flows are implemented **inside the vendored add-on**. Our code sets the same inputs the
Blender panel would set and calls the add-on's operator. If our code looks like it duplicates
add-on logic, that is a defect — see `vendor/jimeng_blender_uploader/UPSTREAM.md`.
