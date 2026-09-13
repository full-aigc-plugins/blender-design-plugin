# Codex Blender Harness Runtime Verification

**Date:** 2026-09-12  
**Platform:** macOS Apple Silicon  
**Blender:** 5.2.1 LTS (`9e2066aef7ef`)

## Verified

| Gate | Status | Evidence |
|---|---|---|
| Harness command core | PASS | 7 real Blender commands, revision 0→7 |
| Managed foreground mode | PASS | Blender launched without Add-on installation; UDS request roundtrip created `ManagedSphere` |
| Connector lifecycle | PASS | Generated zip installed/enabled in Blender 5.2, source mode start/descriptor/revoke/unregister passed; test installation removed afterward |
| Main-thread dispatch | PASS | transport-thread request completes only when Blender timer pumps queue |
| Milestone preview | PASS | fresh camera/front/side/top PNGs with independent SHA-256 |
| BLEND export | PASS | non-empty file + SHA-256 receipt |
| GLB export | PASS | non-empty file + SHA-256 receipt |
| GLTF export | PASS | non-empty file + SHA-256 receipt |
| FBX export | PASS | non-empty file + SHA-256 receipt |
| OBJ export | PASS | non-empty file + SHA-256 receipt |
| STL export | PASS | non-empty file + SHA-256 receipt |
| PNG export | PASS | real camera render |
| JPG export | PASS | real camera render |

## Not yet accepted

| Gate | Status | Reason |
|---|---|---|
| H.264 MP4 | PASS macOS | Blender PNG sequence encoded by ffmpeg 9.0.1/libx264; ffprobe confirmed H.264, even dimensions, 24fps, duration, and size |
| Transaction integration | PASS macOS | Real managed session created an object, injected a failure, reopened the checkpoint, removed the object, and restored revision 0 |
| Model re-import validation | PASS macOS | BLEND/GLB/GLTF/FBX/OBJ/STL were independently opened/imported and contained meshes |
| Windows x64 managed mode | NOT RUN | Requires Windows host and Named Pipe implementation/runtime proof |
| Windows x64 Connector | NOT RUN | Requires Windows Blender host |
| Skill structure validation | PASS | Repository validator checked all eight names, frontmatter blocks, and descriptions |
| Upstream Skill quick validation | BLOCKED | Bundled validator cannot import its undeclared `yaml` dependency on this host |

## Runtime artifacts

- `/private/tmp/codex-blender-harness-smoke/design.blend`
- `/private/tmp/codex-blender-export-smoke/`
- `/private/tmp/codex-blender-media-smoke/`
- `/private/tmp/codex-blender-milestone-smoke/`
- `/private/tmp/codex-blender-connector.zip`

These are temporary verification artifacts, not distributed plugin content.

## Cross-plugin contract

The preview receipt adapter was executed against the real `codex-dreamina-3d` handoff validator.
After aligning `producer_version` with the published `0.1.x` range, validation returned no errors.
This proves receipt compatibility only; a real H.264 preview remains blocked by the encoder gate.

## Idea-to-artifact acceptance

A managed session created an orange desktop speaker from structured commands:

- 12 mutations covering meshes, bevel, two PBR materials, assignment, camera, and two lights;
- transaction commit at scene revision 12;
- camera/front/side/top milestone receipt;
- action-bound authorization for each final export;
- verified `speaker.blend`, `speaker.glb`, and `speaker.png` receipts;
- isolated GLB re-import with 5 meshes and 5 materials.

Visual inspection confirmed the body, grille, knob, materials, and lighting were rendered. The
camera image cropped part of the lower product edge, correctly demonstrating that artifact
validity and visual-design acceptance remain separate gates.
