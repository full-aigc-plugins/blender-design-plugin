# Codex Blender Plugin

<img src="assets/logo.png" alt="Codex Blender logo" width="128">

> Compatibility foundation for safe, reviewable Blender automation in Codex.

[English](README.md) | [简体中文](README.zh-CN.md)

## Status

The Blender workflows, distribution, and preview-only Dreamina 3D adapter are implemented. Blender 5.2.1 LTS runtime acceptance passed for a local Workbench MP4; Maya and paid Seedance generation remain separate gates.

## Purpose

`codex-blender` lets Codex inspect authorized `.blend` projects, prepare cameras and frame ranges, export Workbench or viewport preview video, validate the artifact, and restore temporary scene settings. Its `bin/blender_adapter` preview-only contract renders a local MP4 for `codex-dreamina-3d` without starting the Jimeng upload bridge.

```text
Codex request
  -> capability and permission check
  -> Blender background process + Python bridge
  -> scene inspection / preview render
  -> media validation
  -> local MP4 + structured receipt
```

## Capabilities

- Blender executable and version discovery without automatic installation.
- Read-only scene, camera, animation, material, and output inspection.
- White-model, material-preview, and existing-video workflows.
- Workbench preview rendering with guaranteed scene-state restoration.
- Resolution, frame range, frame rate, codec, duration, and size validation.
- Stable receipts consumable by `dreamina-3d`.

## Safety boundaries

- No automatic Blender, add-on, ffmpeg, or Python-package installation.
- No remote upload, browser control, or paid generation.
- No execution of untrusted `.blend` scripts without explicit authorization.
- Temporary scene mutations must be recorded and restored in `finally` paths.
- Output paths must remain inside a user-approved directory.

## Documentation

- [Architecture](docs/Codex-Blender-Plugin-Architecture.md)
- [架构文档](docs/Codex-Blender-Plugin-Architecture.zh_CN.md)
- [Technical solution](docs/Codex-Blender-Plugin-Technical-Solution.md)
- [技术方案](docs/Codex-Blender-Plugin-Technical-Solution.zh_CN.md)
- [Design specification](docs/superpowers/specs/2026-09-11-codex-blender-plugin-design.md)
- [Implementation plan](docs/superpowers/plans/2026-09-11-codex-blender-plugin-implementation.md)

## Verification target

The first implementation is accepted only after unit tests, fixture-based scene tests, media validation, restoration tests, plugin validation, and an explicitly authorized Blender runtime smoke test pass.

## License

Apache-2.0 — see [LICENSE](LICENSE).
