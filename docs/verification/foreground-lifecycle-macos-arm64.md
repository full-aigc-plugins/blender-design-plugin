# Foreground Lifecycle Commands -- macOS arm64 Acceptance

Scope: Blender 5.2.1 LTS / macOS (darwin) / arm64 / managed mode.  This
evidence covers **only** these five foreground-only commands.  It does not
claim coverage of other Blender versions, platforms, or runtime modes.
Task 4's coverage matrix is the mechanism for other combinations.

Session: `fg-accept-172632`, launched via `scripts/launch_harness.py` with
`--execution-mode auto_with_budget`.  A real Blender GUI window opened on the
host desktop (expected and required for foreground commands).  No addons
installed, no network calls, no telemetry.

## Commands exercised

| Command | Evidence | Result |
|---------|----------|--------|
| `view.set` | 4 calls with orientations FRONT, SIDE, TOP, CAMERA | All succeeded |
| `view.focus` | Called with target object `FgAcceptFocusTarget` (created via `object.create_mesh`) | Succeeded |
| `view.present` | Called once; returned `windowCount: 2` | Succeeded |
| `playback.set` | Two calls: `{playing: true}` then `{playing: false}` | `true` then `false` as expected |
| `preview.capture` | Called with `snapshotId` from `transaction.begin` / `object.create_mesh` / `transaction.commit`; `milestone: foreground-certification`, `width: 256`, `height: 256` | Succeeded; 4 views rendered |

## preview.capture visual evidence

Milestone snapshot `snapshot-9ded457afa6ac4b1f9e22bc8` produced 4 PNG renders
under `<output-root>/milestones/snapshot-9ded457afa6ac4b1f9e22bc8/`.  SHA-256
checksums (verified on disk):

| View | SHA-256 |
|------|---------|
| camera.png | `c858bb68b9bc87d2903d26b7d7b4c64a182ce06691e709bdbf438ddf83f2b7d7` |
| front.png | `b0e0dc1e03dcca835664d2a8ce6ef647f718aa533d992f1b1b621361d76ed6c3` |
| side.png | `437e6011de0491ffcffc3f07e79a238b5ba3ac4e6681625c8680a267ca66b5bc` |
| top.png | `06f53a53698630500ca990991448882898263e77370c3716bedc38c244a490bb` |

The PNGs are not committed to the repository (too large); the checksums above
seal this specific run.  Blender rendering is not guaranteed deterministic
(frame counters, GPU state, sampling), so a re-run is expected to produce
equivalent artifacts for the same scene but not necessarily identical bytes.

## Acceptance script

`tests/runtime/foreground_lifecycle_acceptance.py` drives all 5 commands over
a live foreground session via the Harness transport and writes a
machine-readable report.  It is opt-in (not discovered by `unittest discover`).

## Production-profile verdict

After graduating these 5 commands, `production.status` for identity
`(5.2.1, darwin, arm64, managed)` reports `l1Commands == []` and
`status == 'ready'`.

## Limitations

- This evidence is Blender 5.2.1 / macOS arm64 only.  The production-profile
  validator does **not** check `RuntimeIdentity`; it relies on the catalog
  comment and this document to make scope visible.
- The visual evidence (PNG renders) has not undergone human aesthetic review.
  The sha256 checksums confirm the files were produced by the acceptance run.
- No Blender process was left running after the acceptance.
