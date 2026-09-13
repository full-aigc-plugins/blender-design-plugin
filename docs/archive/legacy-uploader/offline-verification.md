# Offline Verification Evidence

**Date:** 2026-09-12
**Branch:** feat/codex-blender-plugin-v1
**Commit:** `2fb2ce35f1d1167523ead385acd81d6f34315f14`

## Test Suite

```bash
python3 -m unittest discover -s tests -v
```

Result: **163/163 tests pass**. Injected failure tests exercise the official operators, whose
upstream error handler prints expected tracebacks; the suite exits successfully but is not silent.

## Distribution Validation

```bash
python3 scripts/validate_distribution.py
```

Result: **PASS** — all checks green:
- `.codex-plugin/plugin.json` exists with all required fields
- `schemas/scene_receipt.schema.json` exists
- `schemas/artifact_receipt.schema.json` exists
- Four Skills exist in `skills/`
- `vendor/jimeng_blender_uploader/UPSTREAM.md` records all 13 vendored upstream hashes
- No binaries above 1 MiB
- No symlinks
- No secret patterns detected

## Vendored Provenance

```bash
python3 -m unittest tests/test_vendored_core.py -v
```

Result: every file listed in `UPSTREAM.md` matches the sibling official package byte-for-byte;
the five original core hashes also match the plan's provenance block.

## Anti-Drift Guard

`tests/test_vendored_core.py` parses hashes from `UPSTREAM.md`, asserts every vendored file
matches, and compares the distributed files against the sibling official package. A future edit
to a vendored file without updating provenance fails the suite.

## Git Hygiene

```bash
git diff --check
```

Result: **clean** — no whitespace errors.

## Runtime Acceptance

**Status:** `BLOCKED_MISSING_AUTHORIZED_RUNTIME`

Blender is not installed on this host (`command -v blender` returns empty). The plan permits this terminal state. A runtime smoke test requires an explicitly authorized Blender executable and cannot be inferred from unit tests.

## Files

| File | Purpose |
|---|---|
| `.codex-plugin/plugin.json` | Plugin manifest |
| `.agents/plugins/marketplace.json` | Repository marketplace entry |
| `schemas/*.schema.json` | Receipt schemas |
| `vendor/jimeng_blender_uploader/` | Complete vendored official add-on except ffmpeg runtime |
| `vendor/jimeng_blender_uploader/UPSTREAM.md` | Provenance record |
| `scripts/blender_bridge.py` | Inspection + dispatch + restoration observation |
| `scripts/blender_runner.py` | Safe process runner |
| `scripts/codex_bridge.py` | Thin driver: enables the vendored add-on, calls its operators |
| `scripts/validate_document.py` | Schema validator |
| `scripts/validate_distribution.py` | Distribution validator |
| `skills/codex-blender-*/SKILL.md` | Four Codex Skills |
| `tests/` | 163 tests |
| `tests/scenarios/*.md` | Six scenario descriptions |

## Codex plugin spec conformance (checked against codex-rs)

The manifests were audited against Codex's own manifest handling
(`codex-rs/plugin/src/plugin_id.rs`, `core-plugins/src/manifest.rs`,
`core-plugins/src/marketplace.rs`, `exec-server-protocol/src/protocol.rs`).

Rules that are enforced as hard errors, and now satisfied:

| Rule | Source |
|---|---|
| Manifest discovered at `.codex-plugin/plugin.json` | `DISCOVERABLE_PLUGIN_MANIFEST_PATHS` |
| `name` allows only ASCII letters, digits, `.`, `_`, `-`; no leading/trailing/double dot | `validate_plugin_segment` |
| `skills` starts with `./`, is never `./`, contains no `..`, stays inside the plugin root | `resolve_manifest_path` |
| `interface.defaultPrompt` carries at most 3 prompts of at most 128 characters | `MAX_DEFAULT_PROMPT_COUNT` / `MAX_DEFAULT_PROMPT_LEN` |
| Marketplace manifest has a valid `name` and a non-empty `plugins` array | `RawMarketplaceManifest` |
| Each marketplace plugin entry has `name` and `source`; `name` must equal the manifest name | `store.rs` manifest/marketplace name check |

Findings that were fixed:

1. **`name` held a display name.** It was `"Codex Blender"`; a space is not an allowed
   character, so Codex would have rejected the plugin. The identifier is now `codex-blender`
   and the display name lives in `interface.displayName`.
2. **The marketplace manifest was structurally invalid.** It had no `plugins` array (a required
   field) and instead carried invented `id` / `plugin` keys. It now declares
   `plugins: [{name, source: {source: "local", path: "./"}, category}]`.
3. **Invented manifest keys** `id` and `entryPoint` were removed. (`license`, `repository`,
   `author` and `homepage` are kept: Codex's manifest struct has no `deny_unknown_fields`, so
   they are accepted as conventional metadata — the same shape the installed
   `codex-dreamina-3d` plugin uses.)

The repository includes Apache-2.0 `LICENSE`; upstream source rights remain a separately
disclosed distribution caveat in `THIRD_PARTY_NOTICES.md` and `UPSTREAM.md`.
