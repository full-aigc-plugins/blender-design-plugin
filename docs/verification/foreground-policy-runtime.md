# Foreground control and policy runtime — 2026-09-13

Scope: the first two approved Blender-only optimization items. Companion code,
paid generation, motion-quality upgrades and asynchronous export are not changed.

## Real Blender evidence

Blender 5.2.1 LTS, macOS Apple Silicon. Tests were executed against this working
tree in separate foreground processes, leaving existing creative project files intact.

| Gate | Result | Evidence |
|---|---|---|
| Managed policy reaches the live session | PASS | Descriptor and `session.status` report auto_with_budget and blend/png scope |
| Real design through public commands | PASS | New object, material, transform, frame range and location keyframes |
| Camera/front/side/top, focus and playback | PASS | Public command responses; duplicate playback=true remains playing |
| Pause/resume | PASS | Mutation denied while paused; resume requires reinspection |
| Automatic fresh-file export | PASS | New foreground_demo.blend written without a per-export claim |
| Existing-file protection | PASS | Repeated export refused; first file retained |
| Readonly dispatch | PASS | Object creation and export rejected; scene inventory unchanged |
| Connector shared lifecycle | PASS | 37-command real foreground run through Connector runtime, including present-window idempotence |
| Native panel operators | PASS | Blender registered panel; pause/resume, view change and frame jump return FINISHED with verified state changes |
| User-file load revocation | UNIT PASS | External load closes runtime, descriptor and handler; command-owned restore does not revoke |
| Windows foreground behavior | NOT RUN | No Windows runtime exercised in this increment |

Local evidence files (not shipped inside the plugin):

- `/Users/wandl/workspaces/workspace-partme-ai/deliverables/foreground-policy-smoke/auto-report.json` — 35 operations.
- `/Users/wandl/workspaces/workspace-partme-ai/deliverables/foreground-policy-readonly-smoke/readonly-report.json` — 6 operations.
- `/Users/wandl/workspaces/workspace-partme-ai/deliverables/foreground-policy-connector-smoke/connector-report.json` — 37 operations.
- `/Users/wandl/workspaces/workspace-partme-ai/deliverables/foreground-policy-ui-smoke/ui-report.json` — native Blender operator checks.

The OS computer-use inventory selected a different pre-existing Blender instance
during screenshot attempts. No screenshot is claimed as proof of these sessions.
The gates above derive from actual target-process Blender operators and public
Harness responses. Cross-instance OS window activation remains a limitation:
`view.present` opens one target-session review window and reuses it, but does
not guarantee OS focus on every later call.

## Reproduce

Launch a fresh foreground process using `scripts/launch_harness.py`, providing
`--session-id`, `--runtime-dir`, `--output-root`, and `--execution-mode`.
Then run `tests/runtime/foreground_smoke.py --descriptor <file> --report <file>`;
for review_only add `--read-only`. Paths must be new test output directories.

`tests/runtime/connector_bootstrap.py` exercises Connector startup without
installing an Add-on or writing Preferences. `tests/runtime/ui_smoke_bootstrap.py`
executes the real panel operators and leaves the read-only review panel registered.
These scripts are opt-in and are not run by offline test discovery.

## Skill verification

Final local regression: `python3 -m unittest discover -s tests -q` — 172 tests
passed. `scripts/validate_distribution.py`, Connector ZIP packaging and
`git diff --check` passed. Negative distribution fixtures intentionally print
rejection messages; unittest returned exit code zero.

The changed router, design, managed and export Skills pass the installed
skill-creator `quick_validate.py` using the existing Python 3.13/PyYAML runtime.
The command reference removes the contradictory per-milestone automatic approval
instruction and documents inherited routing decisions, typed errors, privacy,
takeover and synchronous-export limits. Structure validation is not claimed as
a separate LLM behavioral benchmark or a perfect TRACE score.

## Limits

- Progress is caller-reported and displayed as such; 100% is not quality acceptance.
- Pause acts between commands; it cannot interrupt an already running synchronous render.
- Users should take over before editing; arbitrary unannounced edits between commands
  are not automatically detected in this increment.
- A takeover invalidates older transactions rather than rolling back user work.
- No public release, cache reinstall or remote runtime verification was performed here.
