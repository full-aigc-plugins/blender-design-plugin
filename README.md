# Codex Blender Plugin

<img src="assets/logo.png" alt="Codex Blender logo" width="128">

> Compatibility foundation for safe, reviewable Blender automation in Codex.

[English](README.md) | [简体中文](README.zh-CN.md)

## Status

The compatibility plugin foundation is now present: manifest, marketplace metadata, brand assets, legal documents, validation script, tests, and implementation directories. Blender workflows and runtime compatibility remain unimplemented and unverified.

## Purpose

`codex-blender` will let Codex inspect authorized `.blend` projects, prepare cameras and frame ranges, export Workbench or viewport preview video, validate the artifact, and restore temporary scene settings. It is a general Blender adapter and does not upload assets to Dreamina or any other service.

```text
Codex request
  -> capability and permission check
  -> Blender background process + Python bridge
  -> scene inspection / preview render
  -> media validation
  -> local MP4 + structured receipt
```

## Planned capabilities

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
