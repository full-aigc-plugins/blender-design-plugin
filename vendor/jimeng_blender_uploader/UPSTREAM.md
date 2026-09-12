# Vendored upstream: `jimeng_blender_uploader`

This directory is a **byte-identical vendored copy** of the official Jimeng/Seedance 2.5
Blender add-on's Python package. It is vendored so the Codex integration drives the add-on's
own logic headlessly instead of reimplementing it.

**Upstream package:** `jimeng_blender_uploader`
**Upstream version:** 1.0.0
**Build:** macOS / CN package (`jimeng_blender_uploader-mac-cn-1.0.0.zip`)
**Local source:** `../jimeng_blender_uploader` (a sibling of this repository). The upstream
project itself is the canonical source.

## Integration principle — read this before changing anything

Everything the two user-facing flows need already lives in this package. Our code *registers*
this add-on inside Blender and *calls its operators*:

- camera render → `JIMENG_OT_render_upload` (`bpy.ops.jimeng.render_upload`)
- local upload → `JIMENG_OT_upload_existing` (`bpy.ops.jimeng.upload_existing`)

Both operators already own: protocol fetching and validation, frame-range derivation and
validation, the render call, file-size validation, link production, the camera-keyed link
cache, and the user-visible error taxonomy.

**Do not reimplement any of that in this repository.** If our code appears to duplicate logic
that exists here, that is a defect to be fixed by delegating here — not by editing this file.

## Vendored files and upstream SHA-256

| File | SHA-256 |
|---|---|
| `__init__.py` | `b9531fc9c74818abc0e024194c71d05250be3203caf5c519afa7c5847ba4a86d` |
| `dcc_config.py` | `d559a7d3202a0621bc986e3069f6069d3a2c400908377fc521b6a20f75663cc4` |
| `operators.py` | `b8f79e27bef4d1bf6403493bd151e6659cfe0c72122d20197f2b20307dcd128a` |
| `panel.py` | `5f05e89049962c4d465df3b76089a327ad1b45668531ef29c0a3eca208053618` |
| `settings.py` | `69454485ff3db83acb05145899af166398a132927b96203565ff42f78b598db8` |
| `state.py` | `52ecf928a1f64f6f5aae1898d548658c836760eeb39ede708194f4e58e2e31bc` |
| `upload_bridge.py` | `714d34aa2426e8a2f2fba61cb3fca54cf4f60e6252e7e79079b4471c68593393` |
| `variant.py` | `3e6fa3b54953634ff44aa3df0f00774ab7279644d8b12c3d49d8c4e174c7fba3` |
| `viewport_render.py` | `b9f1e6fcecd1ca704262f407fb9854540b37f6aab28a2635f3f0c8567f5f252b` |
| `helpers/jimeng_upload/local_bridge.js` | `23fadf12cbb8862264a3738f25e6107bf9247d26bbcf086b40937094628cc571` |
| `helpers/jimeng_upload/package.json` | `a40a0481ee2500a6eaf890b6d6e952aeb9d7f4ebe8aa2305844deaa0c66cfbd7` |
| `helpers/jimeng_upload/package-lock.json` | `9c71ab75cb41bcbfb586da90a7bfc23cfbdac6d5121eb81554424db105a74089` |
| `helpers/jimeng_upload/README.md` | `3749376558bd21650ad34d472fecc5c5f7c27d5f3e0656ec15468c54d739ebd5` |

`tests/test_vendored_core.py` parses this table and asserts every vendored file still hashes to
its recorded value. Editing a vendored file without updating this table fails the suite.

## Why the full package is vendored

An earlier revision vendored only the `bpy`-free subset and reimplemented the orchestration in
our own code. That was wrong — it duplicated validation and flow logic that already exists
here. The full package is vendored instead, because:

- `__init__.py`'s `register()` is the only place the scene properties and operator classes are
  registered; calling it is how a headless driver enables the add-on.
- `operators.py` holds both flows in full, plus the frame-range and error-taxonomy helpers.
- `state.py` holds the link and input-signature state those operators use.
- `panel.py` is UI only, but `register()` calls `panel.register()`; vendoring it keeps
  `register()` byte-identical and working. Registering a `Panel` class is legal in
  `--background` mode — only *drawing* a panel needs a UI context.

The package is closed under imports: everything it needs is `bpy` or the standard library.

## Excluded from vendoring

| Excluded | Reason |
|---|---|
| `runtime/ffmpeg/macos-aarch64/ffmpeg` (~49 MB) and `runtime/ffmpeg/macos-x86_64/ffmpeg` (~76 MB) | ~120 MB of platform binaries; this repository does not bundle ffmpeg. `upload_bridge._bundled_ffmpeg_candidates()` finds nothing and falls through to `JIMENG_UPLOADER_FFMPEG`, then the system `ffmpeg`. |
| `runtime/ffmpeg/LICENSE-imageio-ffmpeg.txt`, `runtime/ffmpeg/VERSION`, `runtime/ffmpeg/README-imageio-ffmpeg-binaries.md` | Belong to the excluded binaries; the bundled payload was `imageio-ffmpeg==0.6.0`. |

`helpers/jimeng_upload/` **is** vendored even though it is a Node helper we never execute,
because `upload_bridge.run_ffmpeg()` passes `cwd=helper_dir()` — the directory must exist for
ffmpeg conversion of non-MP4 inputs to work. That is a filesystem requirement, not a runtime
dependency; the legacy Node bridge is never launched by this repository.

## License and provenance caveat

This repository has **no LICENSE file yet** — license selection is an open decision for the
maintainer. Upstream ships no LICENSE for its Python code; the only license file in the upstream
package covers its bundled ffmpeg binaries (see the exclusion table). Vendoring third-party code
is therefore a provenance fact a maintainer must resolve before any distribution claim.

## Known limitation

`variant.py` is a *generated* build artefact: it pins region `cn`, platform `mac`, language
`zh_cn`, `TARGET_URL = https://jimeng.jianying.com/ai-tool/home`, and the localized strings. It
is vendored verbatim as the baseline for this revision. Other region/platform builds are out of
scope; they need the corresponding generated variant rather than an edit here.
