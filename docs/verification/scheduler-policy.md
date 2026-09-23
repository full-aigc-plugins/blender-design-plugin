# Scheduler Policy Verification (Task 12)

**Scope:** `job.estimate`, `job.list`, `job.events`, and the seven scheduler
policies enforced by `scripts/harness/scheduler.py`.  Evidence gathered through
unit tests on the Python-level scheduler and JobManager; no live Blender
subprocess is launched for these tests.

## Commands Verified

| Command | Risk | Maturity | Evidence |
|---------|------|----------|----------|
| `job.estimate` | read | L3 | `tests/test_job_scheduler.py` |
| `job.list` | read | L3 | `tests/test_job_scheduler.py` |
| `job.events` | read | L3 | `tests/test_job_scheduler.py` |

## Dispatch counts

| Command | Count | Notes |
|---------|-------|-------|
| `job.estimate` | 1 | dispatched through registry, result returned |
| `job.list` | 1 | dispatched through registry with an approved output root |
| `job.events` | 1 | dispatched through registry, result returned |
| **Total** | **3** | |

## Seven scheduler policies

### Policy 1: Maximum active jobs = 2

- `Scheduler(max_active=2)`, three jobs submitted.
- Measured: `active_count=2`, `queued_ids=1`, `process_factory` called 2 times.
- Mutation proof: `test_MUTATION_limit_set_to_three_all_three_active` -- with
  `max_active=3`, all three jobs are active and nothing is queued, proving the
  limit is enforced.

### Policy 2: FIFO queuing

- Two jobs enqueued with `enqueue_time` 1.0 and 2.0 (same priority).
- Measured: `queued_ids=["job_old", "job_new"]` -- older entry first.
- After `try_dispatch` with 1 slot: `job_old` launched, `job_new` still queued.
- Mutation proof: `test_MUTATION_LIFO_would_launch_newest_first` -- reversing
  the queue causes `job_new` to launch instead, proving FIFO order is real.

### Policy 3: Priority reorders queued only

- Two jobs at priority 0; `job_high` promoted to priority 10 via
  `promote_queued("job_high", new_priority=10)`.
- Measured: queue reorders to `["job_high", "job_low"]`.
- A running job's priority raised via `set_running_priority` does not preempt it
  (covered by Policy 4 tests).

### Policy 4: No preemption of running jobs

- One job submitted with `max_active=1` -> launches immediately (`state="running"`).
- Second job submitted with `priority=10` -> queued, not preempting.
- Measured: `active_ids=["job_p4_first"]`, `factory.call_count=1`.
- Proof: `test_running_job_survives_new_submission` and
  `test_raising_priority_of_running_job_changes_nothing` both assert the running
  job stays active after the higher-priority submission and after a priority
  change.  These are the genuine no-preemption tests.

### Policy 5: Disk reserve max(20%, 20 GB)

- **200 GB volume**: 20% = 40.0 GB > 20 GB floor.  Measured:
  `compute_disk_reserve(200*1024^3) = 42,949,672,960 bytes (40.0 GB)`.
- **50 GB volume**: 20% = 10.0 GB < 20 GB floor.  Measured:
  `compute_disk_reserve(50*1024^3) = 21,474,836,480 bytes (20.0 GB)`.
- `check_disk_space` with `reserve_fraction=0, reserve_minimum=0` on `/tmp`:
  `ok=True, free>0, reserve=0`.

### Policy 6: Disk full blocks snapshot + process start

- `Scheduler(disk_reserve_minimum=999*1024^3)` -- absurdly high reserve.
- `submit({...})` raises `HarnessError("DISK_RESERVE_EXCEEDED")`.
- Measured: no snapshot file on disk, `process_factory` called 0 times.
- Mutation proof: `test_MUTATION_bypass_reserve_allows_snapshot_and_process` --
  with `reserve_minimum=0`, the snapshot is saved and a process starts.

### Policy 7: Log rotation 50 MiB x 5 rotations

- Production constants verified: `LOG_MAX_BYTES=52,428,800` (50 MiB),
  `LOG_ROTATION_COUNT=5`.
- **Injected limit test (100 bytes):**
  - 50 bytes written, `rotate_log(max_bytes=100)`: file unchanged (50 bytes).
  - 150 bytes written, `rotate_log(max_bytes=100)`: current log truncated to 0,
    `.log.1` backup contains 150 bytes.
- **Chain shift test (10-byte limit, 3 cycles):**
  - After 3 rotations: `.log.1`, `.log.2`, `.log.3` all exist.
- **No-op on missing file:** `rotate_log` on a nonexistent path does not crash.
- Mutation proof: `test_MUTATION_inject_limit_zero_always_rotates` -- with
  `max_bytes=0`, even 4 bytes triggers rotation (current truncated to 0).

Note on injected vs. production limits: The50 MiB x 5 production constants are
asserted by `test_production_constants_are_50mib_and_5`.  The rotation logic is
exercised with injected limits (100 bytes, 10 bytes) because writing 250 MiB in
a unit test is impractical and unnecessary -- the rotation algorithm is
parameterised and the injected limits exercise every code path.

## job.estimate monotonicity

- `RENDER_STILL` 256x256 vs 1024x1024:
  - disk: 266,240 < 4,198,400 (15.8x)
  - time: 0.005s < 0.084s (16.8x)
  - memory: 537,145,789 < 541,268,958
- `RENDER_ANIMATION_FRAMES` 10 vs 100 frames (1920x1080):
  - disk: 82,984,960 < 829,849,600 (10x)
  - time: 1.659s < 16.589s (10x)
- Schema conformance: output passes the draft-07 JSON Schema validator in
  `schemas/resource_estimate_receipt.schema.json`.

## job.list

- Dispatched through the registry with an approved output root.
- Measured fields: `total` (int), `items` (list of status dicts), `nextOffset`
  (int or null).
- Pagination: `limit=1` returns 1 item with `nextOffset != None`.
- State filtering: `state="completed"` returns only completed jobs.
- Invalid state raises `INVALID_ARGUMENT`.

## job.events

- Dispatched through the registry.
- Measured fields: `events` (list of event dicts with `revision`, `jobId`,
  `type`).
- `afterRevision` filter: returns only events with `revision > afterRevision`.

## What is not verified

- No live Blender subprocess is launched; the `_FakeProcess` and
  `_CountingProcessFactory` stubs are used.
- No real disk I/O for the50 MiB rotation -- exercised at injected limits.
- `job.list` only lists jobs seeded on disk by `_seed_jobs`; it does not verify
  listing of jobs created through a full `submit -> complete` lifecycle (that
  path is covered by `tests/runtime/p3_job_smoke.py`).
- No network calls; no third-party dependencies beyond the standard library.
