---
name: blender-visual-loop
description: Iterate a Blender scene against a target image with immutable screenshots, structured visual verdicts, explicit transaction commit or rollback, and either single-agent or judge-subagent orchestration.
---

# Blender visual loop

Use this workflow when the user supplies a target image or asks for repeated visual refinement.
It coordinates the visual state machine released in PartMe Blender MCP `0.7.0-rc.1`; it does
not replace the Blender domain Skills that perform modeling, lighting, materials, or camera work.

## Preconditions

1. Call `blender_connection_status`, then confirm the catalog contains all of:
   `blender_scene_screenshot`, `blender_visual_loop_create`,
   `blender_visual_loop_status`, `blender_visual_loop_record_capture`,
   `blender_visual_loop_record_verdict`, and `blender_visual_loop_cancel`.
2. Confirm the session has an approved output root. Keep every screenshot path relative to that
   root and unique; screenshot files are immutable and an existing path is rejected.
3. Inspect the scene and record its live `sceneRevision`. Do not guess revisions.
4. Establish the user's acceptance threshold and round budget. Default to `minimumScore: 8`,
   `maxRounds: 20`, `stallWindow: 2`, and `minimumImprovement: 1` only when the user supplied no
   stricter criteria.

For a local target already inside an authorized input or output root, pass `targetPath`. For a
remote client or a file that Blender cannot read directly, pass bounded Base64 PNG/JPEG bytes as
`targetData`. Provide exactly one. Keep the returned target SHA-256 as the target identity for the
entire run.

## Transactional loop

The visual loop reports transaction advice but never commits or rolls back by itself. The client
owns that decision.

1. Open one milestone transaction with `blender_transaction_begin`; retain its transaction ID.
2. Create the loop with `blender_visual_loop_create`. Send the transaction envelope required by
   the tool and the chosen target plus thresholds.
3. Apply the next bounded scene changes inside the same open transaction, always carrying the
   current scene revision.
4. Capture `visual-loops/<loopId>/round-<N>.png` with `blender_scene_screenshot`. Verify the
   structured receipt, SHA-256, dimensions, `restoration.status: confirmed`, and the returned MCP
   image content block. A screenshot is a file write but must not advance the scene revision.
5. Call `blender_visual_loop_record_capture` with `loopId`, the screenshot receipt as `artifact`,
   and `transactionId`. Use that same value for the MCP `_transactionId` envelope.
6. Judge the locked target and current capture. Submit only these four scores, each from 0 to 10:
   `composition`, `lighting`, `materials`, and `details`. Also provide bounded `issues`, concrete
   `nextActions`, and `judge` with `type: human` or `type: agent`. Do not submit a total; the
   runtime computes the arithmetic mean.
7. Call `blender_visual_loop_record_verdict` for the current round and obey its explicit state:

   - `accepted` + `recommendedAction: commit`: commit the pending transaction, then verify the
     final loop status and artifacts.
   - `active` + `recommendedAction: revise`: keep the transaction open, apply only the returned
     next actions, advance the revision chain, and start the next uniquely named capture.
   - `stalled` or `exhausted` + `recommendedAction: rollback`: roll back the pending transaction
     and report the best round, best score, unresolved issues, and artifact receipt.
   - `cancelled`: roll back the pending transaction and stop immediately.

Never commit before a verdict. Never begin another capture while the previous capture lacks a
verdict. Never retry around `VISUAL_TARGET_CHANGED`, `IMAGE_ARTIFACT_CHANGED`,
`VISUAL_VERDICT_REQUIRED`, or a transaction/revision error; inspect status and recover explicitly.

## Judge strategies

### Client with subagents

The orchestrator alone owns Blender MCP calls, the revision chain, and the open transaction.
Give a judge subagent only the locked target, current screenshot, acceptance brief, and required
VisualVerdict schema. It returns scores, issues, and next actions; it must not mutate Blender,
commit, roll back, or trigger providers. The orchestrator validates and records that verdict.

A separate builder subagent may propose bounded changes, but the orchestrator serializes every
mutation. Do not let multiple agents write to the same Blender session or transaction concurrently.

### Client without subagents

Run the identical sequence in one conversation: inspect, mutate, capture, compare, record verdict,
then follow the returned action. Separate the builder and judge phases in the transcript so the
judge evaluates the image rather than defending the just-completed edit. Persisted loop status
allows the same client to resume after reconnecting.

## Human review, cost, and cancellation

If the user requested human judgment, pause after the capture and present the exact target hash,
round, screenshot, and four score fields. Record a human verdict only after receiving it.

The Runtime does not call a vision model. Invoking an external or paid judge/provider requires the
user's existing authorization and cost ceiling; visual-loop creation is not authorization for a
paid submission. Preserve provider cancellation semantics independently from
`blender_visual_loop_cancel`.

On user cancellation, call `blender_visual_loop_cancel`, then explicitly roll back the pending
transaction. If Blender disconnected, reconnect, call `blender_visual_loop_status`, and reconcile
the reported `pendingTransactionId` before doing more work.

## Completion report

Return the loop ID, locked target SHA-256, final state, threshold, score history, best round and
score, committed or rolled-back transaction ID, final scene revision, and every retained artifact
path plus SHA-256. State whether the judge was human, the same agent, or a separate agent. A score
alone is not completion evidence: include the transaction receipt and verified final screenshot.
