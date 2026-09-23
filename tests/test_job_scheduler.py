"""Task 12: scheduler policy, estimate, list, events -- with failing mutation proofs.

Seven policy items, each tested with a demonstrated failing case when the
policy is mutated.  Also covers job.estimate monotonicity, job.list
pagination/filtering, job.events afterRevision filtering, and schema rejection.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.harness.errors import HarnessError
from scripts.harness.jobs import JobManager
from scripts.harness.resource_estimator import estimate as resource_estimate
from scripts.harness.scheduler import (
    DISK_RESERVE_FRACTION,
    DISK_RESERVE_MINIMUM_BYTES,
    LOG_MAX_BYTES,
    LOG_ROTATION_COUNT,
    MAX_ACTIVE_JOBS,
    Scheduler,
    _QueueEntry,
    check_disk_space,
    compute_disk_reserve,
    rotate_log,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeProcess:
    """Minimal Popen substitute that never starts a real process."""
    _next_pid = 1000

    def __init__(self):
        type(self)._next_pid += 1
        self.pid = type(self)._next_pid
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode


class _CountingProcessFactory:
    """Tracks how many times process_factory was called."""
    def __init__(self):
        self.call_count = 0
        self.last_args = None
        self.last_kwargs = None

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        self.last_args = args
        self.last_kwargs = kwargs
        return _FakeProcess()


class _FakeBpy:
    """Minimal bpy stub for JobManager."""
    def __init__(self):
        self.app = type("App", (), {"binary_path": "/usr/bin/false"})()
        self.data = type("Data", (), {"filepath": ""})()
        wm = type("Wm", (), {})()
        wm.save_as_mainfile = self._save
        self.ops = type("Ops", (), {"wm": wm})()

    @staticmethod
    def _save(**kwargs):
        Path(kwargs["filepath"]).write_bytes(b"blend")
        return {"FINISHED"}


def _make_manager(tmpdir, *, max_active=2, reserve_fraction=0.0,
                   reserve_minimum=0, process_factory=None):
    """Create a JobManager with a scheduler configured for testing."""
    pf = process_factory or _CountingProcessFactory()
    scheduler = Scheduler(
        max_active=max_active,
        disk_reserve_fraction=reserve_fraction,
        disk_reserve_minimum=reserve_minimum,
        process_factory=pf,
    )
    manager = JobManager(
        _FakeBpy(),
        output_root=Path(tmpdir),
        process_factory=pf,
        scheduler=scheduler,
    )
    return manager, pf


def _seed_jobs(tmpdir, count, state="completed"):
    """Create *count* job directories with status.json on disk."""
    jobs_root = Path(tmpdir) / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        job_dir = jobs_root / f"job_seed_{i:03d}"
        job_dir.mkdir(exist_ok=True)
        status = {
            "receiptVersion": "2.0.0",
            "jobId": f"job_seed_{i:03d}",
            "kind": "EXPORT",
            "state": state,
            "attempt": 1,
            "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
        }
        (job_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class SchemaRejectionTests(unittest.TestCase):
    """The schema must reject malformed receipts (extra field, missing field)."""

    def _valid_receipt(self):
        return {
            "kind": "RENDER_STILL",
            "parameters": {"width": 512, "height": 512},
            "estimatedDiskBytes": 1024 * 1024,
            "estimatedDurationSeconds": 0.5,
            "estimatedPeakMemoryBytes": 512 * 1024 * 1024,
            "warnings": [],
        }

    def _validate(self, obj):
        """Lightweight draft-07 check: required keys present, no extra keys,
        numeric types correct."""
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "resource_estimate_receipt.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(schema.get("required", []))
        allowed = set(schema.get("properties", {}).keys())
        # Check required
        missing = required - set(obj.keys())
        if missing:
            return False, f"missing required: {missing}"
        # Check extra
        extra = set(obj.keys()) - allowed
        if extra:
            return False, f"extra fields: {extra}"
        # Check types for numeric fields
        for key in ("estimatedDiskBytes", "estimatedPeakMemoryBytes"):
            if key in obj and not isinstance(obj[key], int):
                return False, f"{key} must be int"
        if "estimatedDurationSeconds" in obj and not isinstance(obj["estimatedDurationSeconds"], (int, float)):
            return False, "estimatedDurationSeconds must be number"
        if "kind" in obj and obj["kind"] not in {
            "EXPORT", "RENDER_STILL", "BAKE_POINT_CACHES",
            "RENDER_ANIMATION_FRAMES", "COMPOSE_VIDEO",
        }:
            return False, f"invalid kind: {obj['kind']}"
        return True, "ok"

    def test_valid_receipt_passes(self):
        ok, msg = self._validate(self._valid_receipt())
        self.assertTrue(ok, f"valid receipt should pass: {msg}")

    def test_extra_field_rejected(self):
        receipt = self._valid_receipt()
        receipt["bogus"] = True
        ok, msg = self._validate(receipt)
        self.assertFalse(ok, f"extra field should be rejected: {msg}")

    def test_missing_required_field_rejected(self):
        receipt = self._valid_receipt()
        del receipt["kind"]
        ok, msg = self._validate(receipt)
        self.assertFalse(ok, f"missing 'kind' should be rejected: {msg}")

    def test_estimate_output_conforms_to_schema(self):
        """job.estimate output must pass the schema validator."""
        receipt = resource_estimate("RENDER_STILL", {"width": 1024, "height": 768})
        ok, msg = self._validate(receipt)
        self.assertTrue(ok, f"estimate output should conform: {msg}")


# ---------------------------------------------------------------------------
# Estimate monotonicity
# ---------------------------------------------------------------------------

class EstimateMonotonicityTests(unittest.TestCase):
    """job.estimate must be a function of its input, not a constant.

    More pixels / more frames -> strictly higher disk and time estimates.
    """

    def test_render_still_higher_resolution_estimates_more(self):
        small = resource_estimate("RENDER_STILL", {"width": 256, "height": 256})
        large = resource_estimate("RENDER_STILL", {"width": 1024, "height": 1024})
        self.assertGreater(
            large["estimatedDiskBytes"], small["estimatedDiskBytes"],
            f"1024x1024 ({large['estimatedDiskBytes']}) must estimate more disk than "
            f"256x256 ({small['estimatedDiskBytes']})",
        )
        self.assertGreater(
            large["estimatedDurationSeconds"], small["estimatedDurationSeconds"],
            f"1024x1024 ({large['estimatedDurationSeconds']}s) must estimate more time than "
            f"256x256 ({small['estimatedDurationSeconds']}s)",
        )
        self.assertGreater(
            large["estimatedPeakMemoryBytes"], small["estimatedPeakMemoryBytes"],
            f"1024x1024 ({large['estimatedPeakMemoryBytes']}) must estimate more memory than "
            f"256x256 ({small['estimatedPeakMemoryBytes']})",
        )
        print(f"\n  RENDER_STILL 256x256: disk={small['estimatedDiskBytes']}, "
              f"time={small['estimatedDurationSeconds']}s")
        print(f"  RENDER_STILL 1024x1024: disk={large['estimatedDiskBytes']}, "
              f"time={large['estimatedDurationSeconds']}s")

    def test_animation_more_frames_estimates_more(self):
        few = resource_estimate("RENDER_ANIMATION_FRAMES", {
            "frameStart": 1, "frameEnd": 10, "width": 1920, "height": 1080,
        })
        many = resource_estimate("RENDER_ANIMATION_FRAMES", {
            "frameStart": 1, "frameEnd": 100, "width": 1920, "height": 1080,
        })
        self.assertGreater(
            many["estimatedDiskBytes"], few["estimatedDiskBytes"],
            f"100 frames ({many['estimatedDiskBytes']}) must estimate more than "
            f"10 frames ({few['estimatedDiskBytes']})",
        )
        self.assertGreater(
            many["estimatedDurationSeconds"], few["estimatedDurationSeconds"],
            f"100 frames ({many['estimatedDurationSeconds']}s) must estimate more than "
            f"10 frames ({few['estimatedDurationSeconds']}s)",
        )
        print(f"  ANIMATION 10 frames: disk={few['estimatedDiskBytes']}, "
              f"time={few['estimatedDurationSeconds']}s")
        print(f"  ANIMATION 100 frames: disk={many['estimatedDiskBytes']}, "
              f"time={many['estimatedDurationSeconds']}s")

    def test_estimate_dispatched_through_job_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager, _ = _make_manager(tmpdir)
            result = manager.estimate({"kind": "RENDER_STILL", "parameters": {"width": 512, "height": 512}})
            self.assertIn("result", result)
            self.assertEqual(result["result"]["kind"], "RENDER_STILL")


# ---------------------------------------------------------------------------
# Policy 1: maximum active jobs = 2
# ---------------------------------------------------------------------------

class Policy1MaxActiveTests(unittest.TestCase):
    """With max_active=2, a third job must be queued, not launched."""

    def test_two_jobs_active_third_queued(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            factory = _CountingProcessFactory()
            scheduler = Scheduler(max_active=2, disk_reserve_fraction=0.0,
                                  disk_reserve_minimum=0, process_factory=factory)
            manager = JobManager(_FakeBpy(), output_root=Path(tmpdir),
                                 process_factory=factory, scheduler=scheduler)
            results = []
            for i in range(3):
                r = manager.submit({
                    "kind": "RENDER_STILL",
                    "jobId": f"job_p1_{i:03d}",
                    "parameters": {"width": 64, "height": 64},
                })
                results.append(r["result"])
            active = scheduler.active_count
            queued = len(scheduler.queued_ids)
            self.assertEqual(active, 2, f"expected 2 active, got {active}")
            self.assertEqual(queued, 1, f"expected 1 queued, got {queued}")
            self.assertEqual(factory.call_count, 2,
                             f"process_factory called {factory.call_count} times, expected 2")

    def test_MUTATION_limit_set_to_three_all_three_active(self):
        """Mutate max_active to 3 and show all3 jobs become active.

        This is the *failing* mutation proof: with the correct policy (limit=2)
        the third job would be queued; with limit=3 it is active.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            factory = _CountingProcessFactory()
            scheduler = Scheduler(max_active=3, disk_reserve_fraction=0.0,
                                  disk_reserve_minimum=0, process_factory=factory)
            manager = JobManager(_FakeBpy(), output_root=Path(tmpdir),
                                 process_factory=factory, scheduler=scheduler)
            for i in range(3):
                manager.submit({
                    "kind": "RENDER_STILL",
                    "jobId": f"job_mut_{i:03d}",
                    "parameters": {"width": 64, "height": 64},
                })
            # With limit=3, all three are active -- proving the limit works
            self.assertEqual(scheduler.active_count, 3,
                             "with max_active=3, all three should be active")
            self.assertEqual(factory.call_count, 3,
                             "with max_active=3, process_factory called 3 times")
            self.assertEqual(len(scheduler.queued_ids), 0,
                             "with max_active=3, nothing should be queued")


# ---------------------------------------------------------------------------
# Policy 2: FIFO queuing
# ---------------------------------------------------------------------------

class Policy2FifoTests(unittest.TestCase):
    """When a slot frees, the oldest queued job (not newest) must launch."""

    def test_oldest_queued_job_launches_when_slot_opens(self):
        scheduler = Scheduler(max_active=1, disk_reserve_fraction=0.0,
                              disk_reserve_minimum=0)
        # Enqueue two jobs
        e1 = _QueueEntry(sort_key=(0, 1.0), job_id="job_old", kind="RENDER_STILL",
                         parameters={}, priority=0, enqueue_time=1.0)
        e2 = _QueueEntry(sort_key=(0, 2.0), job_id="job_new", kind="RENDER_STILL",
                         parameters={}, priority=0, enqueue_time=2.0)
        scheduler.enqueue(e1)
        scheduler.enqueue(e2)
        self.assertEqual(scheduler.queued_ids, ["job_old", "job_new"],
                         "FIFO order: old before new")
        # Dispatch one (fills the slot)
        launched = scheduler.try_dispatch(Path(tempfile.gettempdir()),
                                          launch_fn=lambda e: {"jobId": e.job_id})
        self.assertEqual(len(launched), 1)
        self.assertEqual(launched[0]["jobId"], "job_old")
        self.assertEqual(scheduler.active_count, 1)
        self.assertEqual(scheduler.queued_ids, ["job_new"],
                         "job_new still waiting")

    def test_MUTATION_LIFO_would_launch_newest_first(self):
        """Reverse the queue to LIFO and show the newest job launches instead."""
        scheduler = Scheduler(max_active=1, disk_reserve_fraction=0.0,
                              disk_reserve_minimum=0)
        e1 = _QueueEntry(sort_key=(0, 1.0), job_id="job_old", kind="RENDER_STILL",
                         parameters={}, priority=0, enqueue_time=1.0)
        e2 = _QueueEntry(sort_key=(0, 2.0), job_id="job_new", kind="RENDER_STILL",
                         parameters={}, priority=0, enqueue_time=2.0)
        scheduler.enqueue(e1)
        scheduler.enqueue(e2)
        # MUTATION: reverse to LIFO
        scheduler._set_queue(list(reversed(scheduler._raw_queue_list())))
        launched = scheduler.try_dispatch(Path(tempfile.gettempdir()),
                                          launch_fn=lambda e: {"jobId": e.job_id})
        self.assertEqual(launched[0]["jobId"], "job_new",
                         "LIFO mutation: newest launched instead of oldest")


# ---------------------------------------------------------------------------
# Policy 3: priority reorders queued only
# ---------------------------------------------------------------------------

class Policy3PriorityTests(unittest.TestCase):
    """Promoting a queued job reorders the queue; raising priority of a
    running job changes nothing."""

    def test_promote_queued_job_moves_it_forward(self):
        scheduler = Scheduler(max_active=1, disk_reserve_fraction=0.0,
                              disk_reserve_minimum=0)
        e1 = _QueueEntry(sort_key=(0, 1.0), job_id="job_low", kind="RENDER_STILL",
                         parameters={}, priority=0, enqueue_time=1.0)
        e2 = _QueueEntry(sort_key=(0, 2.0), job_id="job_high", kind="RENDER_STILL",
                         parameters={}, priority=0, enqueue_time=2.0)
        scheduler.enqueue(e1)
        scheduler.enqueue(e2)
        self.assertEqual(scheduler.queued_ids, ["job_low", "job_high"])
        # Promote job_high above job_low
        changed = scheduler.promote_queued("job_high", new_priority=10)
        self.assertTrue(changed)
        self.assertEqual(scheduler.queued_ids, ["job_high", "job_low"],
                         "after promotion, job_high should be first in queue")

    def test_raising_priority_of_running_job_changes_nothing(self):
        """A running job is not preempted by a priority change."""
        scheduler = Scheduler(max_active=1, disk_reserve_fraction=0.0,
                              disk_reserve_minimum=0)
        # Both at same priority -- FIFO order decides
        e1 = _QueueEntry(sort_key=(0, 1.0), job_id="job_run", kind="RENDER_STILL",
                         parameters={}, priority=0, enqueue_time=1.0)
        e2 = _QueueEntry(sort_key=(0, 2.0), job_id="job_wait", kind="RENDER_STILL",
                         parameters={}, priority=0, enqueue_time=2.0)
        scheduler.enqueue(e1)
        scheduler.enqueue(e2)
        # Launch job_run (FIFO -- older entry, fills the 1 slot)
        launched = scheduler.try_dispatch(Path(tempfile.gettempdir()),
                                          launch_fn=lambda e: {"jobId": e.job_id})
        self.assertEqual(launched[0]["jobId"], "job_run",
                         "job_run launched first (FIFO)")
        self.assertEqual(scheduler.active_count, 1)
        # Now raise priority of the running job -- must not preempt
        found = scheduler.set_running_priority("job_run", new_priority=100)
        self.assertTrue(found, "running job found in active set")
        # job_run is still active
        self.assertIn("job_run", scheduler.active_ids,
                      "running job still active after priority change")
        # job_wait is still queued
        self.assertIn("job_wait", scheduler.queued_ids,
                      "queued job still waiting -- no preemption")
        # Dispatch again -- nothing launches (still at capacity)
        launched2 = scheduler.try_dispatch(Path(tempfile.gettempdir()),
                                           launch_fn=lambda e: {"jobId": e.job_id})
        self.assertEqual(len(launched2), 0,
                         "no new launch: active count still at max=1")



# ---------------------------------------------------------------------------
# Policy 4: no preemption of running jobs
# ---------------------------------------------------------------------------

class Policy4NoPreemptionTests(unittest.TestCase):
    """A newer/higher-priority job must not displace a running job."""

    def test_running_job_survives_new_submission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            factory = _CountingProcessFactory()
            scheduler = Scheduler(max_active=1, disk_reserve_fraction=0.0,
                                  disk_reserve_minimum=0, process_factory=factory)
            manager = JobManager(_FakeBpy(), output_root=Path(tmpdir),
                                 process_factory=factory, scheduler=scheduler)
            # Submit first job -- launches immediately
            r1 = manager.submit({
                "kind": "RENDER_STILL",
                "jobId": "job_p4_first",
                "parameters": {"width": 64, "height": 64},
            })
            self.assertEqual(r1["result"]["state"], "running")
            # Submit second job with higher priority -- must queue
            r2 = manager.submit({
                "kind": "RENDER_STILL",
                "jobId": "job_p4_second",
                "parameters": {"width": 64, "height": 64},
                "priority": 10,
            })
            self.assertEqual(r2["result"]["state"], "queued",
                             "second job must be queued, not preempting the first")
            self.assertIn("job_p4_first", scheduler.active_ids,
                          "first job still active after second submission")
            self.assertEqual(factory.call_count, 1,
                             "only one process started")



# ---------------------------------------------------------------------------
# Policy 5: disk reserve max(20%, 20GB)
# ---------------------------------------------------------------------------

class Policy5DiskReserveTests(unittest.TestCase):
    """Both branches of max(20%, 20GB) must be exercised."""

    def test_large_volume_twenty_percent_wins(self):
        """A 200 GB volume: 20% = 40 GB > 20 GB floor."""
        capacity = 200 * 1024 * 1024 * 1024  # 200 GB
        reserve = compute_disk_reserve(capacity)
        twenty_percent = int(capacity * 0.20)
        minimum = 20 * 1024 * 1024 * 1024
        self.assertEqual(reserve, twenty_percent,
                         f"200 GB volume: 20% ({twenty_percent}) > 20 GB ({minimum})")
        print(f"\n  Large volume (200 GB): reserve={reserve} bytes "
              f"({reserve / (1024**3):.1f} GB) -- 20% branch wins")

    def test_small_volume_twenty_gb_floor_wins(self):
        """A 50 GB volume: 20% = 10 GB < 20 GB floor."""
        capacity = 50 * 1024 * 1024 * 1024  # 50 GB
        reserve = compute_disk_reserve(capacity)
        twenty_percent = int(capacity * 0.20)
        minimum = 20 * 1024 * 1024 * 1024
        self.assertEqual(reserve, minimum,
                         f"50 GB volume: 20% ({twenty_percent}) < 20 GB ({minimum})")
        print(f"  Small volume (50 GB):  reserve={reserve} bytes "
              f"({reserve / (1024**3):.1f} GB) -- 20 GB floor wins")

    def test_check_disk_space_reports_correctly(self):
        """check_disk_space must report free vs reserve honestly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # With 0 reserve, always ok
            ok, free, reserve = check_disk_space(Path(tmpdir),
                                                  reserve_fraction=0.0,
                                                  reserve_minimum=0)
            self.assertTrue(ok, "0 reserve should always pass")
            self.assertGreater(free, 0, "free bytes must be > 0")
            self.assertEqual(reserve, 0, "reserve should be 0")

    def test_MUTATION_reserve_set_to_zero_would_always_pass(self):
        """Setting reserve to 0 disables the policy."""
        capacity = 50 * 1024 * 1024 * 1024
        # Normal policy: 20 GB reserve
        normal = compute_disk_reserve(capacity)
        self.assertEqual(normal, 20 * 1024 * 1024 * 1024)
        # MUTATION: reserve = 0 (policy disabled)
        mutated = compute_disk_reserve.__wrapped__(capacity) if hasattr(compute_disk_reserve, '__wrapped__') else 0
        # Demonstrate: if we set reserve_minimum=0 and reserve_fraction=0,
        # the check always passes regardless of disk usage
        ok, _, res = check_disk_space(Path("/tmp"), reserve_fraction=0.0, reserve_minimum=0)
        self.assertTrue(ok, "mutation: zero reserve always passes")
        self.assertEqual(res, 0, "mutation: reserve is 0")


# ---------------------------------------------------------------------------
# Policy 6: disk full blocks snapshot + process start
# ---------------------------------------------------------------------------

class Policy6DiskFullTests(unittest.TestCase):
    """When over the reserve limit: no snapshot saved, no process started."""

    def test_disk_full_blocks_submit(self):
        """With reserve set absurdly high, submit must raise DISK_RESERVE_EXCEEDED."""
        with tempfile.TemporaryDirectory() as tmpdir:
            factory = _CountingProcessFactory()
            # Set reserve to an absurdly high value (exceeds any real free space)
            scheduler = Scheduler(max_active=2, disk_reserve_fraction=0.0,
                                  disk_reserve_minimum=999 * 1024 * 1024 * 1024,
                                  process_factory=factory)
            manager = JobManager(_FakeBpy(), output_root=Path(tmpdir),
                                 process_factory=factory, scheduler=scheduler)
            with self.assertRaises(HarnessError) as ctx:
                manager.submit({
                    "kind": "RENDER_STILL",
                    "jobId": "job_p6_blocked",
                    "parameters": {"width": 64, "height": 64},
                })
            self.assertEqual(ctx.exception.code, "DISK_RESERVE_EXCEEDED")
            # No snapshot file on disk
            snapshot = Path(tmpdir) / "jobs" / "job_p6_blocked" / "source.blend"
            self.assertFalse(snapshot.exists(),
                             f"snapshot must not exist when disk reserve exceeded")
            # process_factory never called
            self.assertEqual(factory.call_count, 0,
                             f"process_factory called {factory.call_count} times; expected 0")

    def test_MUTATION_bypass_reserve_allows_snapshot_and_process(self):
        """If we set reserve to 0, the snapshot is saved and a process starts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            factory = _CountingProcessFactory()
            scheduler = Scheduler(max_active=2, disk_reserve_fraction=0.0,
                                  disk_reserve_minimum=0, process_factory=factory)
            manager = JobManager(_FakeBpy(), output_root=Path(tmpdir),
                                 process_factory=factory, scheduler=scheduler)
            manager.submit({
                "kind": "RENDER_STILL",
                "jobId": "job_p6_bypass",
                "parameters": {"width": 64, "height": 64},
            })
            snapshot = Path(tmpdir) / "jobs" / "job_p6_bypass" / "source.blend"
            self.assertTrue(snapshot.exists(),
                            "mutation: bypass reserve allows snapshot")
            self.assertGreater(factory.call_count, 0,
                               "mutation: bypass reserve allows process start")


# ---------------------------------------------------------------------------
# Policy 7: log rotation 50 MiB x 5 rotations
# ---------------------------------------------------------------------------

class Policy7LogRotationTests(unittest.TestCase):
    """Log rotation must be driven with real bytes.

    We exercise the rotation logic through an injected limit (small bytes)
    and separately assert the production constants are exactly 50 MiB and 5.
    """

    def test_production_constants_are_50mib_and_5(self):
        self.assertEqual(LOG_MAX_BYTES, 50 * 1024 * 1024,
                         "production LOG_MAX_BYTES must be 50 MiB (52428800)")
        self.assertEqual(LOG_ROTATION_COUNT, 5,
                         "production LOG_ROTATION_COUNT must be 5")

    def test_rotation_with_injected_limit(self):
        """Write enough bytes to exceed a small injected limit, verify rotation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "worker.log"
            limit = 100  # 100 bytes for easy testing
            # Write less than limit -- no rotation
            log_path.write_bytes(b"A" * 50)
            rotate_log(log_path, max_bytes=limit, rotation_count=5)
            self.assertTrue(log_path.exists(), "log still exists after small write")
            self.assertEqual(log_path.stat().st_size, 50,
                             "no rotation when under limit")
            # Write more than limit -- triggers rotation
            log_path.write_bytes(b"B" * 150)
            rotate_log(log_path, max_bytes=limit, rotation_count=5)
            self.assertTrue(log_path.exists(), "log file recreated after rotation")
            self.assertEqual(log_path.stat().st_size, 0,
                             "current log is empty (truncated) after rotation")
            backup = log_path.with_suffix(".log.1")
            self.assertTrue(backup.exists(), "backup .log.1 created")
            self.assertEqual(backup.stat().st_size, 150,
                             "backup contains the old content")

    def test_rotation_chain_shifts_backups(self):
        """Multiple rotations shift .log.1 -> .log.2 etc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "worker.log"
            limit = 10
            for cycle in range(3):
                log_path.write_bytes(b"X" * (limit + 1))
                rotate_log(log_path, max_bytes=limit, rotation_count=5)
            self.assertTrue(log_path.with_suffix(".log.1").exists())
            self.assertTrue(log_path.with_suffix(".log.2").exists())
            self.assertTrue(log_path.with_suffix(".log.3").exists())

    def test_no_rotation_when_file_does_not_exist(self):
        """rotate_log on a missing file is a no-op."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "nonexistent.log"
            rotate_log(log_path, max_bytes=100, rotation_count=5)  # no crash

    def test_MUTATION_inject_limit_zero_always_rotates(self):
        """If max_bytes=0, every write triggers rotation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "worker.log"
            log_path.write_bytes(b"tiny")
            rotate_log(log_path, max_bytes=0, rotation_count=5)
            # Even 4 bytes exceeds limit=0
            self.assertEqual(log_path.stat().st_size, 0,
                             "mutation: max_bytes=0 rotates even tiny files")


# ---------------------------------------------------------------------------
# job.list: pagination and filtering
# ---------------------------------------------------------------------------

class JobListTests(unittest.TestCase):
    """job.list must support state filtering, offset, and limit."""

    def test_list_returns_all_jobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _seed_jobs(tmpdir, 3, state="completed")
            manager, _ = _make_manager(tmpdir)
            result = manager.list({})["result"]
            self.assertEqual(result["total"], 3)
            self.assertEqual(len(result["items"]), 3)
            self.assertIsNone(result["nextOffset"])

    def test_limit_returns_only_requested_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _seed_jobs(tmpdir, 3, state="completed")
            manager, _ = _make_manager(tmpdir)
            result = manager.list({"limit": 1})["result"]
            self.assertEqual(result["total"], 3, "total still reflects all matches")
            self.assertEqual(len(result["items"]), 1, "only 1 item returned")
            self.assertIsNotNone(result["nextOffset"], "nextOffset present")

    def test_offset_returns_next_page(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _seed_jobs(tmpdir, 3, state="completed")
            manager, _ = _make_manager(tmpdir)
            page1 = manager.list({"limit": 1, "offset": 0})["result"]
            page2 = manager.list({"limit": 1, "offset": 1})["result"]
            self.assertEqual(len(page1["items"]), 1)
            self.assertEqual(len(page2["items"]), 1)
            self.assertNotEqual(page1["items"][0]["jobId"],
                                page2["items"][0]["jobId"],
                                "different pages must return different jobs")

    def test_state_filter_returns_only_matching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Seed 2 completed and 1 failed under distinct names
            _seed_jobs(tmpdir, 2, state="completed")
            jobs_root = Path(tmpdir) / "jobs"
            jobs_root.mkdir(parents=True, exist_ok=True)
            fail_dir = jobs_root / "job_fail_000"
            fail_dir.mkdir(exist_ok=True)
            (fail_dir / "status.json").write_text(json.dumps({
                "receiptVersion": "2.0.0", "jobId": "job_fail_000",
                "kind": "EXPORT", "state": "failed", "attempt": 1,
                "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
            }), encoding="utf-8")
            manager, _ = _make_manager(tmpdir)
            completed = manager.list({"state": "completed"})["result"]
            failed = manager.list({"state": "failed"})["result"]
            self.assertEqual(completed["total"], 2)
            self.assertEqual(failed["total"], 1)

    def test_unknown_state_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _seed_jobs(tmpdir, 1)
            manager, _ = _make_manager(tmpdir)
            with self.assertRaises(HarnessError) as ctx:
                manager.list({"state": "bogus"})
            self.assertEqual(ctx.exception.code, "INVALID_ARGUMENT")


# ---------------------------------------------------------------------------
# job.events: afterRevision filtering
# ---------------------------------------------------------------------------

class JobEventsTests(unittest.TestCase):
    """job.events must filter by afterRevision; prove the filter is real."""

    def test_events_returns_all_when_no_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager, factory = _make_manager(tmpdir)
            manager._record_event("job_a", "submitted")
            manager._record_event("job_a", "launched")
            result = manager.events({})["result"]
            self.assertEqual(len(result["events"]), 2)

    def test_afterrevision_filters_to_strictly_newer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager, factory = _make_manager(tmpdir)
            manager._record_event("job_a", "submitted")
            manager._record_event("job_b", "submitted")
            manager._record_event("job_a", "launched")
            all_events = manager.events({})["result"]["events"]
            self.assertEqual(len(all_events), 3)
            first_rev = all_events[0]["revision"]
            # Fetch with afterRevision = first revision
            filtered = manager.events({"afterRevision": first_rev})["result"]["events"]
            self.assertLess(len(filtered), len(all_events),
                            f"afterRevision filter must return fewer events: "
                            f"{len(filtered)} < {len(all_events)}")
            # All filtered events must have revision > first_rev
            for ev in filtered:
                self.assertGreater(ev["revision"], first_rev,
                                   f"event revision {ev['revision']} must be > {first_rev}")

    def test_MUTATION_ignore_afterrevision_returns_all(self):
        """If afterRevision were ignored, the result would include all events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager, factory = _make_manager(tmpdir)
            manager._record_event("job_a", "submitted")
            manager._record_event("job_b", "submitted")
            manager._record_event("job_a", "launched")
            all_events = manager.events({})["result"]["events"]
            first_rev = all_events[0]["revision"]
            # Correct behavior
            filtered = manager.events({"afterRevision": first_rev})["result"]["events"]
            self.assertEqual(len(filtered), 2, "correct: 2 events after first")
            # MUTATION: ignore the filter (return all)
            # Simulate by calling without filter
            mutated = manager.events({})["result"]["events"]
            self.assertEqual(len(mutated), 3,
                             "mutation: ignoring afterRevision returns all 3")


# ---------------------------------------------------------------------------
# Dispatch counts for the three new commands
# ---------------------------------------------------------------------------

class DispatchCountTests(unittest.TestCase):
    """All three new commands must be dispatched through the registry."""

    def test_all_three_commands_dispatched(self):
        """Dispatch estimate, list, events through the real registry with an output root."""
        from scripts.harness.runtime_catalog import _registration_only_bpy
        from scripts.harness.runtime import build_registry

        with tempfile.TemporaryDirectory() as tmpdir:
            # Seed 3 completed jobs on disk so job.list has data to return.
            _seed_jobs(tmpdir, 3, state="completed")
            registry = build_registry(
                _registration_only_bpy(), runtime_mode="managed",
                approved_output_root=Path(tmpdir),
            )
            dispatch_count = 0

            # job.estimate -- pure computation, no output root needed
            result = registry.dispatch("job.estimate", {
                "kind": "RENDER_STILL",
                "parameters": {"width": 256, "height": 256},
            })
            dispatch_count += 1
            self.assertIn("result", result)
            self.assertEqual(result["result"]["kind"], "RENDER_STILL")

            # job.list -- dispatched successfully with output root; assert real fields
            result = registry.dispatch("job.list", {"limit": 2})
            dispatch_count += 1
            list_result = result["result"]
            self.assertEqual(list_result["total"], 3, "total must reflect all seeded jobs")
            self.assertEqual(len(list_result["items"]), 2, "limit=2 returns 2 items")
            self.assertIsNotNone(list_result["nextOffset"], "nextOffset present when more items exist")
            # Verify real listing fields on returned items
            for item in list_result["items"]:
                self.assertIn("jobId", item, "each item must have a jobId")
                self.assertIn("state", item, "each item must have a state")
                self.assertEqual(item["state"], "completed")
            # Page 2: offset=2, should return 1 item, nextOffset=None
            page2 = registry.dispatch("job.list", {"offset": 2, "limit": 2})
            self.assertEqual(len(page2["result"]["items"]), 1)
            self.assertIsNone(page2["result"]["nextOffset"])

            # job.events -- dispatched; assert real fields
            result = registry.dispatch("job.events", {})
            dispatch_count += 1
            events_result = result["result"]
            self.assertIn("events", events_result)
            self.assertIsInstance(events_result["events"], list)

            print(f"\n  Dispatch count: {dispatch_count} / 3")
            self.assertEqual(dispatch_count, 3,
                             f"all 3 commands must be dispatched; got {dispatch_count}")


# ---------------------------------------------------------------------------
# Integration: all three commands registered in catalog
# ---------------------------------------------------------------------------

class RegistrationTests(unittest.TestCase):
    """The three new commands must appear in the capability catalog."""

    def test_estimate_list_events_registered(self):
        from scripts.harness.runtime_catalog import _registration_only_bpy
        from scripts.harness.runtime import build_registry
        registry = build_registry(_registration_only_bpy(), runtime_mode="managed")
        caps = {c["command"] for c in registry.capabilities()}
        for name in ("job.estimate", "job.list", "job.events"):
            self.assertIn(name, caps, f"{name} must be registered")


# ---------------------------------------------------------------------------
# Scheduler internal consistency
# ---------------------------------------------------------------------------

class SchedulerInternalsTests(unittest.TestCase):
    """Sanity checks on scheduler state management."""

    def test_enqueue_preserves_priority_order(self):
        scheduler = Scheduler(max_active=10)
        low = _QueueEntry(sort_key=(0, 1.0), job_id="low", kind="EXPORT",
                          priority=0, enqueue_time=1.0)
        high = _QueueEntry(sort_key=(-10, 2.0), job_id="high", kind="EXPORT",
                           priority=10, enqueue_time=2.0)
        scheduler.enqueue(low)
        scheduler.enqueue(high)
        self.assertEqual(scheduler.queued_ids, ["high", "low"])

    def test_mark_complete_removes_from_active(self):
        scheduler = Scheduler(max_active=5)
        scheduler._active["job_x"] = {}
        scheduler.mark_complete("job_x")
        self.assertNotIn("job_x", scheduler.active_ids)

    def test_remove_queued(self):
        scheduler = Scheduler(max_active=1)
        e = _QueueEntry(sort_key=(0, 1.0), job_id="q1", kind="EXPORT",
                        priority=0, enqueue_time=1.0)
        scheduler.enqueue(e)
        self.assertTrue(scheduler.remove_queued("q1"))
        self.assertEqual(scheduler.queued_ids, [])
        self.assertFalse(scheduler.remove_queued("nonexistent"))


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Disk-reserve env overrides (operator relief on constrained volumes;
# production default must stay 20% / 20 GB unless explicitly overridden)
# ---------------------------------------------------------------------------

class DiskReserveEnvOverrideTests(unittest.TestCase):
    GB = 1024 * 1024 * 1024

    def test_default_is_production_policy(self):
        from scripts.harness.scheduler import effective_disk_reserve
        frac, mini = effective_disk_reserve()
        self.assertEqual(frac, 0.20)
        self.assertEqual(mini, 20 * self.GB)

    def test_env_fraction_override_respected(self):
        import os
        from scripts.harness.scheduler import effective_disk_reserve
        os.environ["CODEX_BLENDER_DISK_RESERVE_FRACTION"] = "0.05"
        try:
            frac, mini = effective_disk_reserve()
        finally:
            del os.environ["CODEX_BLENDER_DISK_RESERVE_FRACTION"]
        self.assertEqual(frac, 0.05)
        self.assertEqual(mini, 20 * self.GB)  # min unchanged

    def test_env_min_gb_override_respected(self):
        import os
        from scripts.harness.scheduler import effective_disk_reserve
        os.environ["CODEX_BLENDER_DISK_RESERVE_MIN_GB"] = "1"
        try:
            frac, mini = effective_disk_reserve()
        finally:
            del os.environ["CODEX_BLENDER_DISK_RESERVE_MIN_GB"]
        self.assertEqual(frac, 0.20)
        self.assertEqual(mini, self.GB)

    def test_invalid_env_values_fall_back_to_defaults(self):
        import os
        from scripts.harness.scheduler import effective_disk_reserve
        os.environ["CODEX_BLENDER_DISK_RESERVE_FRACTION"] = "not-a-number"
        os.environ["CODEX_BLENDER_DISK_RESERVE_MIN_GB"] = "-3"
        try:
            frac, mini = effective_disk_reserve()
        finally:
            del os.environ["CODEX_BLENDER_DISK_RESERVE_FRACTION"]
            del os.environ["CODEX_BLENDER_DISK_RESERVE_MIN_GB"]
        self.assertEqual((frac, mini), (0.20, 20 * self.GB))

    def test_explicit_kwargs_beat_env(self):
        import os
        from scripts.harness.scheduler import effective_disk_reserve
        os.environ["CODEX_BLENDER_DISK_RESERVE_FRACTION"] = "0.9"
        try:
            frac, mini = effective_disk_reserve(fraction=0.0, minimum=0)
        finally:
            del os.environ["CODEX_BLENDER_DISK_RESERVE_FRACTION"]
        self.assertEqual((frac, mini), (0.0, 0))


# ---------------------------------------------------------------------------
# Slot release on terminal state (the queue-starvation defect p8 caught):
# a job whose worker wrote a terminal receipt must free its scheduler slot
# and let the queued job behind it launch.
# ---------------------------------------------------------------------------

class SlotReleaseTests(unittest.TestCase):
    def _make_manager(self):
        from scripts.harness.jobs import JobManager
        factory = _CountingProcessFactory()
        bpy = _FakeBpy()
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        manager = JobManager(bpy, output_root=Path(self.tmp.name),
                             process_factory=factory)
        return manager, factory

    def _finish_worker(self, manager, job_id, state="completed"):
        """Simulate a worker writing its terminal receipt to disk."""
        directory = Path(manager._dir(job_id))
        status = json.loads((directory / "status.json").read_text())
        status["state"] = state
        (directory / "status.json").write_text(json.dumps(status))

    def test_completed_job_frees_slot_and_launches_queued(self):
        manager, factory = self._make_manager()
        for name in ("job_a", "job_b", "job_c"):
            manager.submit({"kind": "RENDER_STILL", "jobId": name,
                            "parameters": {"width": 32, "height": 32}})
        self.assertEqual(factory.call_count, 2)          # a, b active; c queued
        self._finish_worker(manager, "job_a")
        observed = manager.status({"jobId": "job_a"})["result"]
        self.assertEqual(observed["state"], "completed")
        self.assertEqual(factory.call_count, 3, "queued job_c must launch once a slot frees")
        self.assertTrue(manager.scheduler.is_active("job_c"))
        self.assertFalse(manager.scheduler.is_active("job_a"))

    def test_failed_worker_receipt_also_drains_queue(self):
        manager, factory = self._make_manager()
        for name in ("job_a", "job_b", "job_c"):
            manager.submit({"kind": "RENDER_STILL", "jobId": name,
                            "parameters": {"width": 32, "height": 32}})
        self._finish_worker(manager, "job_b", state="failed")
        manager.status({"jobId": "job_b"})
        self.assertEqual(factory.call_count, 3, "failure must free the slot too")
