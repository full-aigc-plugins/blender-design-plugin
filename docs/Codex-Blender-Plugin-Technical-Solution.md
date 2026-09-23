# Blender Design Plugin Technical Solution

> **Document control**
>
> | Field | Value |
> | --- | --- |
> | Status | Implemented for `blender-design` `0.3.0`; Windows runtime gates recorded `NOT RUN` |
> | Scope | Technology choices, contracts, configuration precedence, error model, tests, and release rules |
> | Audience | Implementers extending or reviewing this plugin |
> | Runtime evidence | [harness-runtime.md](verification/harness-runtime.md) |

## 1. Decision

Run a guarded local Harness inside the user's own Blender, driven by a closed, versioned JSON command protocol.

### Technology choices

| Choice | Rationale |
| --- | --- |
| Blender Python API only, no C++ or external DCC SDK | The plugin must run inside the user's own Blender 5.2.1 LTS install without a build step |
| Unix Domain Socket on macOS, Named Pipe on Windows, tokenized loopback TCP as fallback | Local transports avoid exposing a port while still covering both release-gate platforms |
| Closed JSON command documents over a versioned protocol | Codex can validate a request before dispatch, and unknown commands fail closed |
| A single command registry shared by both runtime modes | Managed and Connector modes cannot drift into two different capability sets |
| Python 3 `unittest` | No third-party test dependency, so the suite runs in the same environment that runs the plugin |
| Vendored viewport renderer under `vendor/` | Preserves the official uploader's rendering behaviour as isolated research material without reimplementing it |
| Independent media probing via ffprobe | A file that exists is not a file that is correct |

### Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Expose a general Python execution command | Makes arbitrary execution reachable from a model-authored argument |
| Serve the Harness over a network port | Expands the attack surface beyond the local machine for no benefit |
| Install the Connector Add-on automatically | Writes into the user's Blender without consent |
| Trust a command exit code as delivery evidence | An exit code cannot prove the artifact is correct |
| Let the two runtime modes evolve separate registries | Guarantees a silent capability difference between modes |

## 2. Blender discovery and launch

Managed mode resolves the Blender executable, then starts it with a temporary bootstrap script (`managed_bootstrap.py` via `managed_launcher.py`) and no preference or Add-on write. Connector mode performs no launch at all: the Add-on in `connector/codex_blender_connector/` registers inside an already-running Blender and advertises the same protocol.

Both modes then converge on the same discovery handshake: open the transport, exchange the session secret, negotiate `codex-blender/v1`, and publish the capability list from the command registry. `launch_harness.py` and `harness_cli.py` are the entry points Codex uses.

## 3. Command and schema contract

Requests are closed JSON documents. Every request carries `protocolVersion` (`codex-blender/v1`), `sessionId`, a unique `requestId`, a `transactionId`, a registered `command`, a closed `arguments` object, and — for every mutation — `expectedSceneRevision`. A gated operation additionally carries an authorization claim.

Responses carry request status, the new scene revision, changed objects, warnings, the snapshot ID, and structured error information. A repeated `requestId` returns the prior response instead of re-executing.

The JSON Schemas under `schemas/` are the machine-checkable half of that contract:

```text
schemas/artifact_receipt.schema.json
schemas/command.schema.json
schemas/frame_sequence_receipt.schema.json
schemas/milestone_receipt.schema.json
schemas/render_plan.schema.json
schemas/response.schema.json
schemas/video_artifact_receipt.schema.json
```

## 4. Directory layout

```text
.codex-plugin/plugin.json     plugin manifest (id blender-design)
bin/                          executable adapters consumed by sibling plugins
connector/codex_blender_connector/   the Connector Add-on
docs/                         architecture, technical solution, verification evidence
schemas/                      the seven JSON Schemas above
scripts/                      CLI entry points, launchers, validators
scripts/harness/              the transport-neutral Harness core
scripts/harness/commands/     the command registry
skills/                       26 Agent Skills
tests/                        37 test modules
vendor/jimeng_blender_uploader/   archived research material, not a runtime dependency
```

`docs/archive/legacy-uploader/` holds the superseded uploader-era architecture and technical solution. It is retained as history and is never loaded at runtime.

## 5. Interface contracts

| Interface | Contract |
| --- | --- |
| Codex to Harness | closed JSON request over the local transport |
| Harness to Codex | closed JSON response plus artifact receipts |
| Harness to Blender | registered commands executed on the main thread only |
| Blender to sibling plugin | `ArtifactReceipt` `1.0.0` written atomically, plus `bin/` adapters |
| Harness to audit | per-session audit summary and per-export receipts |

Model exports are re-imported into an isolated scene and checked for expected structure. Media outputs are probed independently with ffprobe. A receipt is written only after the artifact passes its own validation.

## 6. Configuration precedence

Highest precedence first:

1. An explicit argument on the current request.
2. The `ExecutionPolicy` envelope carried by the session and recorded in the audit.
3. The launch or Connector option set for the session.
4. The default, which is `interactive`.

An omitted policy remains `interactive` so existing callers keep their behaviour. A narrower policy can never be widened by a later request: a session opened as `review_only` rejects mutation, export, and authorization escalation even if the request carries an authorization claim.

## 7. Error model

| Condition | Outcome |
| --- | --- |
| Unknown command | Fail closed, no dispatch |
| Stale `expectedSceneRevision` | Rejected before mutation |
| Duplicate non-idempotent `requestId` | Prior response returned, no re-execution |
| Path outside an approved root | Rejected after canonical resolution, including symlinks |
| Mid-transaction exception | Transaction rolled back; restoration status reported |
| Validation failure | Halt for recovery; the plan does not continue |
| Missing required asset with proxies forbidden | Stop and request user material |
| Exceeding the envelope (overwrite, delete, expert Python, unapproved path, remote budget) | Stop for action-bound authorization |

Errors are structured, and a localized message is never the branch condition.

## 8. Idempotency and recovery

Milestone approval binds `sceneRevision + snapshotId`, and the final export must use that bound revision. Long animation output is split into two durable jobs: `RENDER_ANIMATION_FRAMES` produces per-frame outputs, and `COMPOSE_VIDEO` consumes only a complete, hash-verified `FrameSequenceReceipt`. Explicit resume reuses verified frames and replaces only missing or corrupt entries, so an interrupted render does not restart from frame zero. Crash recovery reopens the last persistent checkpoint and replays only committed idempotent commands.

## 9. Implementation phases

| Phase | Content |
| --- | --- |
| Harness core | session, guard, main-thread queue, registry, transaction engine |
| Foreground and policy | viewport and playback commands, panel, `ExecutionPolicy` propagation, pause and takeover |
| Capability coverage | the phased P0–P9 domain build-out recorded in the acceptance evidence |
| Media pipeline | frame-sequence rendering, independent ffmpeg composition, compositor and VSE delivery |
| Packaging | Connector zip packaging, Windows x64 Named Pipe and recovery, release gates |

## 10. Test strategy

The suite is written test-first against the published contract. Representative cases:

- A transport-thread request completes only when the Blender timer pumps the queue.
- A mutation with a stale `expectedSceneRevision` is rejected and changes nothing.
- A repeated non-idempotent `requestId` returns the prior response and executes once.
- An injected failure rolls the transaction back and reports restoration status.
- A path that escapes the approved root via a symlink is rejected.
- A `review_only` session rejects mutation even when an authorization claim is present.
- Queue work is rejected after takeover or revoke, including work queued before it.
- `COMPOSE_VIDEO` refuses a `FrameSequenceReceipt` that is incomplete or hash-mismatched.
- Frame and playback changes do not increment the content revision or write scene files.

| Dimension | Coverage |
| --- | --- |
| Test modules | 37 under `tests/` |
| Runtime modes | managed and Connector share one conformance suite |
| Platforms | macOS Apple Silicon verified; Windows x64 required by the release gate |
| Export formats | `.blend`, `.glb`, `.gltf`, `.fbx`, `.obj`, `.stl`, `.png`, `.jpg`, H.264 `.mp4` |
| Failure injection | transaction rollback and crash recovery |
| Skills | 26 Skills validated for structure, and routed by behaviour evaluation |

## 11. Release and rollback

Release requires the conformance suite to pass against both runtime modes, real Blender runtime tests on macOS Apple Silicon and Windows x64, and validated receipts for every release format. Windows x64 managed mode and Connector runtime are recorded as `NOT RUN` in the current evidence because they need a Windows Blender host; they remain release gates, not waived requirements.

Rollback is a first-class runtime behaviour rather than a release-time concern: each milestone is reversible, each mutation is revision-checked, and a failed transaction restores the prior scene state. The distributed artifact is a plugin directory, so downgrading is replacing the directory with the prior version; no migration step runs against the user's scenes.

## 12. Evidence map

| Claim | Evidence |
| --- | --- |
| Harness core and command registry | `scripts/harness/`, `schemas/` |
| Managed and Connector conformance | `tests/` and [harness-runtime.md](verification/harness-runtime.md) |
| Export validation | [harness-runtime.md](verification/harness-runtime.md), independent re-import and probing |
| Capability inventory | [capability-counts.json](verification/capability-counts.json) |
| Uploader-era archive | `docs/archive/legacy-uploader/` |
