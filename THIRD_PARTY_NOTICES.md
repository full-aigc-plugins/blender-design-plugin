# Third-Party Notices

## Vendored source: jimeng_blender_uploader

This repository vendors the Python source of the official Jimeng/Seedance 2.5 Blender add-on,
`jimeng_blender_uploader` version 1.0.0 (the macOS/CN build), under
`vendor/jimeng_blender_uploader/`. It is vendored byte-for-byte so the Codex integration can
drive the add-on's own render, encode, validation, and upload logic headlessly instead of
reimplementing it.

Files included: `__init__.py`, `dcc_config.py`, `operators.py`, `panel.py`, `settings.py`,
`state.py`, `upload_bridge.py`, `variant.py`, `viewport_render.py`, and the
`helpers/jimeng_upload/` directory. Exact upstream SHA-256 values for every file are recorded in
`vendor/jimeng_blender_uploader/UPSTREAM.md` and asserted by `tests/test_vendored_core.py`.

**Licensing status of the vendored source is unresolved.** The upstream package ships no license
file for its Python code — the only license file it contains covers the ffmpeg binaries it
bundles (see below). The Apache-2.0 license of *this* repository does not by itself grant rights
to the vendored third-party source. A maintainer must confirm the upstream terms before any
distribution that includes this directory.

### Excluded from vendoring

The upstream package's bundled ffmpeg binaries (~120 MB, `imageio-ffmpeg==0.6.0`) are **not**
vendored. ffmpeg is resolved from the environment or a system installation, and a missing tool is
reported as `DEPENDENCY_MISSING` rather than downloaded.

## No other bundled components

Beyond the vendored source above, this repository does not bundle third-party application
binaries, proprietary SDKs, credentials, generated media, or other vendor source code.

References to Blender, Autodesk Maya, Jimeng, Dreamina, Seedance, Codex, and other product names
identify interoperability targets. Their trademarks and software remain the property of their
respective owners.
