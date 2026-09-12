# Offline Verification Evidence

**Date:** 2026-09-12
**Branch:** feat/codex-blender-plugin-v1
**Commit:** (see git log)

## Test Suite

```bash
python3 -m unittest discover -s tests -v
```

Result: **145/145 tests pass**, pristine output, no warnings.

## Distribution Validation

```bash
python3 scripts/validate_distribution.py
```

Result: **PASS** — all checks green:
- `.codex-plugin/plugin.json` exists with all required fields
- `schemas/scene_receipt.schema.json` exists
- `schemas/artifact_receipt.schema.json` exists
- Four Skills exist in `skills/`
- `vendor/jimeng_blender_uploader/UPSTREAM.md` records five upstream hashes
- No binaries above 1 MiB
- No symlinks
- No secret patterns detected

## Vendored Provenance

```bash
cd vendor/jimeng_blender_uploader && shasum -a 256 dcc_config.py upload_bridge.py settings.py variant.py viewport_render.py
```

Result: **5/5 hashes match** UPSTREAM.md and the plan's provenance block.

## Anti-Drift Guard

The test `test_vendored_files_hash_to_recorded_values` in `tests/test_vendored_core.py` parses hashes from `UPSTREAM.md` and asserts each vendored file matches. A future edit to a vendored file without updating `UPSTREAM.md` fails the suite.

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
| `vendor/jimeng_blender_uploader/` | Vendored headless core |
| `vendor/jimeng_blender_uploader/UPSTREAM.md` | Provenance record |
| `scripts/blender_bridge.py` | Inspection + export adapter |
| `scripts/blender_runner.py` | Safe process runner |
| `scripts/media_probe.py` | ffprobe-based validation |
| `scripts/jimeng_link.py` | Jimeng link production |
| `scripts/validate_document.py` | Schema validator |
| `scripts/validate_distribution.py` | Distribution validator |
| `skills/codex-blender-*/SKILL.md` | Four Codex Skills |
| `tests/` | 145 tests |
| `tests/scenarios/*.md` | Six scenario descriptions |
