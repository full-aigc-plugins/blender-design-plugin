# Foreground control and execution-policy runtime

Spec: `../specs/2026-09-12-codex-blender-harness-design.md`, foreground increment.
This is the first approved optimization batch; it does not change companion plugins.

- [x] Add failing tests exercising readonly denial, automatic fresh-file export,
  policy validation/propagation, takeover, progress and pending-queue cancellation.
  Files: `tests/test_foreground_policy.py`, `tests/test_managed_mode.py`,
  `tests/test_harness_dispatch.py`, `tests/test_harness_server.py`.
- [x] Implement policy normalization, immutable format/root scope and pre-dispatch
  guards in `scripts/harness/execution_policy.py`, `session.py`, `runtime.py`.
  Check `review_only` with otherwise-valid authorization and confirm no files or objects change.
- [x] Add closed viewport/playback commands, runtime status and ephemeral panel in
  `scripts/harness/commands/view.py`, `scripts/harness/frontend.py`.
  Frame/playback changes must not increment content revisions or write scene files.
- [x] Wire policy into launcher/bootstrap/Connector and implement lifecycle cleanup
  in `server.py`, `main_thread.py`, `managed_launcher.py`, `managed_bootstrap.py`,
  `launch_harness.py`, `connector/codex_blender_connector/{runtime,panel}.py`.
  Queue work must be rejected after takeover/revoke, even if queued beforehand.
- [x] Reconcile Skills and guide with observed behavior. Use installed skill-validation
  tooling and explicit behavior scenarios rather than adding prose substring tests.
- [x] Run focused and full unittest suites, distribution validation and connector packaging.
  In a real foreground Blender process, create/transform objects through the public
  Harness, exercise views/frame/playback, pause/inspect/resume, export a new file,
  and prove readonly rejects a mutation. Record actual evidence and limitations.

Release/install operations are separate from this implementation batch. Existing
foreground user sessions and unrelated local/remote work are preserved.

Evidence: `../../verification/foreground-policy-runtime.md`. Cross-instance OS focus
and preemption of long synchronous operators are explicitly not claimed as solved.
