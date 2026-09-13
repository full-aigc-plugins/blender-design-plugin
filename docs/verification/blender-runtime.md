# Runtime Verification

**Status:** `PASS` — preview-only adapter, 2026-09-13

## Authorized Runtime

- Blender: `5.2.1 LTS`
- Executable: `/Applications/Blender.app/Contents/MacOS/Blender`
- Fixture: temporary Cube + Camera scene, frames 1–48
- Adapter: `bin/blender_adapter`
- Remote/paid actions: none

## Verified Result

```text
schema_version=1.0.0
producer_plugin=codex-blender
artifact_id=blender_smoke_001
codec=h264
container=mp4
dimensions=320x180
fps=24.0
duration_seconds=2.0
bytes=6818
sha256=2a38c024311534e8ddcced9927a9c4fe64a5c05cba91cd5e7879712ebced8e6e
restoration.status=confirmed
adapter.stderr=(empty)
```

## Cross-Plugin Acceptance

`codex-dreamina-3d` invoked the same executable contract through
`request_preview_export`, copied the MP4, independently re-hashed it, and
obtained the same SHA-256. Companion discovery resolved the adapter as callable
in the standard installed-plugin directory shape.

## Boundary

This proves Blender preview generation and the shared receipt gate. It does not
prove Maya, Dreamina authentication, account entitlement, quotation, approval,
paid submission, or final Seedance artifact acceptance.
