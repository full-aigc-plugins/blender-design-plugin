# Upstream Provenance

**Package:** jimeng_blender_uploader
**Version:** 1.0.0
**Build:** jimeng_blender_uploader-mac-cn-1.0.0.zip (macOS, CN region)

## Vendored Files

| file | SHA-256 |
|---|---|
| `dcc_config.py` | `d559a7d3202a0621bc986e3069f6069d3a2c400908377fc521b6a20f75663cc4` |
| `upload_bridge.py` | `714d34aa2426e8a2f2fba61cb3fca54cf4f60e6252e7e79079b4471c68593393` |
| `settings.py` | `69454485ff3db83acb05145899af166398a132927b96203565ff42f78b598db8` |
| `variant.py` | `3e6fa3b54953634ff44aa3df0f00774ab7279644d8b12c3d49d8c4e174c7fba3` |
| `viewport_render.py` | `b9f1e6fcecd1ca704262f407fb9854540b37f6aab28a2635f3f0c8567f5f252b` |

## Excluded Files

| file/directory | reason |
|---|---|
| `__init__.py` | Upstream UI registration (operators, panels, handlers); imports bpy at module level; cannot be imported headless |
| `operators.py` | Blender operator definitions; imports bpy at module level |
| `panel.py` | Blender panel definitions; imports bpy at module level |
| `state.py` | Blender state management; imports bpy at module level |
| `helpers/jimeng_upload/` | Upload helper utilities not required by the headless pipeline |
| `runtime/ffmpeg/*` | Bundled ffmpeg binaries (~120 MB); not distributable |

## License / Provenance Caveat

This repository has no LICENSE file yet (license selection is an open
decision for the maintainer).  The upstream package ships no LICENSE for
its Python code; the only license file in the package covers its bundled
ffmpeg, which is excluded from this vendor.

## Known Limitation

`variant.py` is a generated build artefact pinned to region `cn`,
platform `mac`, language `zh_cn`.  Other region/platform builds are out
of scope for this revision.
