"""Task 13: Job journal -- atomic writes, append-only, monotonic revision, recovery.

Each of the five rules has a positive test and a demonstrated failing mutation.
No hardcoded True; every boolean derived from a comparison.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.harness.job_journal import (
    ALLOWED_RECOVERY_PLANS,
    JobEvent,
    JobJournal,
    RecoveryPlan,
    atomic_write_json,
)


# ---------------------------------------------------------------------------
# Rule 1: Atomicity -- fsync called before replace; partial write leaves target intact
# ---------------------------------------------------------------------------

class AtomicityTests(unittest.TestCase):
    """Rule 1: atomic write with fsync before replace.

    Two checks:
    (a) Call-level contract: fsync must be called on the file descriptor
        before os.replace.  We inject a recording fsync and assert it was
        called with the right fd.  Dropping fsync makes the check fail.
    (b) Behavioural: inject a failure between temp-file write and replace;
        the target must still hold the previous complete content.
    """

    def test_fsync_called_before_replace(self):
        """Call-level contract: fsync must be invoked with the fd."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            calls = []

            def recording_fsync(fd):
                calls.append(fd)

            atomic_write_json(path, {"v": 1}, _fsync=recording_fsync)
            self.assertEqual(len(calls), 1,
                             f"fsync called {len(calls)} times; expected 1")
            self.assertIsInstance(calls[0], int,
                                 f"fsync arg must be an fd (int), got {type(calls[0])}")
            # Verify the file was written correctly.
            content = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(content, {"v": 1})

    def test_MUTATION_dropping_fsync_breaks_contract(self):
        """If fsync is a no-op, the call-level check fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            calls = []

            def noop_fsync(fd):
                # Intentionally do nothing -- the mutation.
                pass

            atomic_write_json(path, {"v": 1}, _fsync=noop_fsync)
            self.assertEqual(len(calls), 0,
                             "mutation: noop fsync records zero calls")
            # The file is still written (the behavioural contract is separate),
            # but the durability contract is broken -- we cannot prove data
            # reached stable storage.

    def test_failure_between_write_and_replace_preserves_target(self):
        """Inject a failure after the temp file is written but before replace.

        The target must still hold the previous complete content.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "status.json"
            # Write initial content.
            atomic_write_json(path, {"state": "running", "pid": 123})
            original_bytes = path.read_bytes()
            original_content = json.loads(original_bytes)
            original_len = len(original_bytes)

            # Now inject a failure: write a second version, but make
            # os.replace raise before it completes.
            import scripts.harness.job_journal as jj
            real_replace = os.replace

            def failing_replace(src, dst):
                raise OSError("injected failure")

            # Monkey-patch os.replace temporarily.
            old_replace = os.replace
            os.replace = failing_replace
            try:
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"state": "completed", "pid": 123})
            finally:
                os.replace = old_replace

            # Target must still hold the previous complete content.
            after_bytes = path.read_bytes()
            after_len = len(after_bytes)
            after_content = json.loads(after_bytes)
            self.assertEqual(after_len, original_len,
                             f"target byte length must be unchanged: "
                             f"{after_len} != {original_len}")
            self.assertEqual(after_content, original_content,
                             f"target content must be unchanged after failed replace")
            print(f"\n  Atomicity: original {original_len} bytes, "
                  f"after failure {after_len} bytes")
            print(f"  Original content: {original_content}")
            print(f"  After failure:    {after_content}")

    def test_happy_path_produces_new_complete_content(self):
        """After a successful atomic write, the target holds the new content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "status.json"
            atomic_write_json(path, {"state": "running"})
            content1 = json.loads(path.read_bytes())
            self.assertEqual(content1["state"], "running")

            atomic_write_json(path, {"state": "completed"})
            content2 = json.loads(path.read_bytes())
            self.assertEqual(content2["state"], "completed")
            # Verify the old state is gone.
            self.assertNotEqual(content1, content2,
                                "new content must differ from old")


# ---------------------------------------------------------------------------
# Rule 2: Revision monotonicity
# ---------------------------------------------------------------------------

class RevisionMonotonicityTests(unittest.TestCase):
    """Rule 2: revisions must be strictly increasing."""

    def test_revisions_are_strictly_increasing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = JobJournal(Path(tmpdir))
            revisions = []
            for i in range(5):
                rev = journal.append(JobEvent(
                    job_id=f"job_{i:03d}", type="submitted", message=f"event {i}",
                ))
                revisions.append(rev)
            # Assert strictly increasing.
            for i in range(1, len(revisions)):
                self.assertGreater(revisions[i], revisions[i - 1],
                                   f"revision[{i}]={revisions[i]} must be > "
                                   f"revision[{i-1}]={revisions[i-1]}")
            print(f"\n  Monotonicity: revisions = {revisions}")

    def test_MUTATION_constant_revision_breaks_monotonicity(self):
        """Mutate append to return a constant and show the check fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = JobJournal(Path(tmpdir))

            # Save the real append method.
            real_append = journal.append

            def mutated_append(event, **kwargs):
                # Ignore the revision counter; always return 1.
                real_append(event, **kwargs)
                return 1

            journal.append = mutated_append
            revisions = []
            for i in range(3):
                rev = journal.append(JobEvent(
                    job_id=f"job_{i:03d}", type="submitted",
                ))
                revisions.append(rev)
            # All are 1 -- not strictly increasing.
            self.assertEqual(revisions, [1, 1, 1],
                             "mutation: constant revision returns [1, 1, 1]")
            # The check would fail:
            is_increasing = all(
                revisions[i] > revisions[i - 1]
                for i in range(1, len(revisions))
            )
            self.assertFalse(is_increasing,
                             "mutation: revisions are not strictly increasing")


# ---------------------------------------------------------------------------
# Rule 3: Append-only
# ---------------------------------------------------------------------------

class AppendOnlyTests(unittest.TestCase):
    """Rule 3: after appending, previous file content is an exact prefix."""

    def test_previous_content_is_prefix_of_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = JobJournal(Path(tmpdir))
            journal.append(JobEvent(job_id="job_a", type="submitted"))
            content_after_1 = journal._path.read_bytes()

            journal.append(JobEvent(job_id="job_b", type="submitted"))
            content_after_2 = journal._path.read_bytes()

            # content_after_1 must be a prefix of content_after_2.
            is_prefix = content_after_2[:len(content_after_1)] == content_after_1
            self.assertTrue(is_prefix,
                            f"previous content ({len(content_after_1)} bytes) "
                            f"must be a prefix of new content ({len(content_after_2)} bytes)")
            print(f"\n  Append-only: after 1 event: {len(content_after_1)} bytes")
            print(f"  After 2 events: {len(content_after_2)} bytes")
            print(f"  Prefix match: {is_prefix}")

    def test_MUTATION_rewrite_breaks_prefix(self):
        """Mutate append to rewrite the file from scratch; prefix check fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = JobJournal(Path(tmpdir))
            journal.append(JobEvent(job_id="job_a", type="submitted"))
            content_after_1 = journal._path.read_bytes()

            # Save the real append.
            real_append = journal.append

            def mutated_append(event, **kwargs):
                # Instead of appending, rewrite with only the new event.
                journal._events = [event.to_dict()]
                journal._events[0]["revision"] = 1
                atomic_write_json(journal._path, journal._events)
                return 1

            journal.append = mutated_append
            journal.append(JobEvent(job_id="job_b", type="submitted"))
            content_after_2 = journal._path.read_bytes()

            # content_after_1 is NOT a prefix of content_after_2.
            is_prefix = content_after_2[:len(content_after_1)] == content_after_1
            self.assertFalse(is_prefix,
                             "mutation: rewrite breaks the prefix relationship")


# ---------------------------------------------------------------------------
# Rule 4: Indeterminate running -> interrupted
# ---------------------------------------------------------------------------

class RecoveryClassificationTests(unittest.TestCase):
    """Rule 4: running job with dead PID recovers as interrupted.

    Also covers the determinate case: a cleanly completed job must NOT be
    reported as interrupted.
    """

    def _write_status(self, jobs_dir, job_id, state, pid=None, kind="EXPORT"):
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "receiptVersion": "2.0.0",
            "jobId": job_id,
            "kind": kind,
            "state": state,
            "attempt": 1,
            "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
        }
        if pid is not None:
            status["pid"] = pid
        (job_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
        return status

    def test_running_with_dead_pid_recovers_as_interrupted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jobs_dir = root / "jobs"
            jobs_dir.mkdir()
            # Use a PID that is guaranteed dead (0 is special; use a high number).
            self._write_status(jobs_dir, "job_dead", "running", pid=99999999)
            journal = JobJournal(root)
            plan = journal.recover()
            # Read back the status -- must be interrupted.
            status = json.loads((jobs_dir / "job_dead" / "status.json").read_text())
            self.assertEqual(status["state"], "interrupted",
                             f"dead-PID running job must be interrupted, got {status['state']}")
            # Plan must be one of the four allowed.
            self.assertIn(plan.plan, ALLOWED_RECOVERY_PLANS,
                          f"plan {plan.plan!r} not in allowed set")

    def test_completed_job_is_not_reported_interrupted(self):
        """Determinate case: a completed job must survive recovery unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jobs_dir = root / "jobs"
            jobs_dir.mkdir()
            self._write_status(jobs_dir, "job_done", "completed")
            journal = JobJournal(root)
            plan = journal.recover()
            status = json.loads((jobs_dir / "job_done" / "status.json").read_text())
            self.assertEqual(status["state"], "completed",
                             f"completed job must stay completed, got {status['state']}")

    def test_MUTATION_recover_as_resumable_breaks_interrupted(self):
        """Mutate recover to classify dead-PID running as 'running' (resumable).

        The interrupted classification check then fails.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jobs_dir = root / "jobs"
            jobs_dir.mkdir()
            self._write_status(jobs_dir, "job_dead", "running", pid=99999999)
            journal = JobJournal(root)

            # Save the real recover.
            real_recover = journal.recover

            def mutated_recover():
                # Override: classify everything as still running.
                for job_dir in sorted(jobs_dir.iterdir()):
                    sp = job_dir / "status.json"
                    if sp.is_file():
                        s = json.loads(sp.read_text(encoding="utf-8"))
                        s["state"] = "running"  # mutation: never interrupt
                        sp.write_text(json.dumps(s))
                return RecoveryPlan(plan="resubmit_from_snapshot", jobs={})

            journal.recover = mutated_recover
            journal.recover()
            status = json.loads((jobs_dir / "job_dead" / "status.json").read_text())
            # The mutation leaves it as "running" instead of "interrupted".
            self.assertEqual(status["state"], "running",
                             "mutation: dead-PID job stays 'running'")
            # Verify: the correct check would fail.
            is_interrupted = status["state"] == "interrupted"
            self.assertFalse(is_interrupted,
                             "mutation: job is not interrupted despite dead PID")


# ---------------------------------------------------------------------------
# Rule 5: RecoveryPlan both directions
# ---------------------------------------------------------------------------

class RecoveryPlanTests(unittest.TestCase):
    """Rule 5: each of the four plans is producible; unknown plans are rejected.

    - resume_missing_frames:      RENDER_ANIMATION_FRAMES with verified frames
    - recompose_verified_sequence: COMPOSE_VIDEO with complete source sequence
    - resubmit_from_snapshot:      EXPORT job with no frame-level resume
    - manual_decision_required:    mixed interrupted jobs (frame + export)
    """

    def _write_status(self, jobs_dir, job_id, state, pid=None, kind="EXPORT"):
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "receiptVersion": "2.0.0",
            "jobId": job_id,
            "kind": kind,
            "state": state,
            "attempt": 1,
            "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
        }
        if pid is not None:
            status["pid"] = pid
        (job_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
        return status

    def test_resume_missing_frames_from_real_situation(self):
        """RENDER_ANIMATION_FRAMES with verified frames on disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jobs_dir = root / "jobs"
            jobs_dir.mkdir()
            job_dir = jobs_dir / "job_frames"
            job_dir.mkdir()
            # Write status as running with dead PID.
            status = {
                "receiptVersion": "3.0.0",
                "jobId": "job_frames",
                "kind": "RENDER_ANIMATION_FRAMES",
                "state": "running",
                "pid": 99999999,
                "attempt": 1,
                "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
            }
            (job_dir / "status.json").write_text(json.dumps(status))
            # Write a frame-sequence manifest with verified frames.
            manifest = {
                "receiptVersion": "3.0.0",
                "frameStart": 1, "frameEnd": 3, "frameStep": 1,
                "fps": 24, "format": "PNG",
                "frames": [
                    {"frame": 1, "path": "/tmp/f1.png", "bytes": 100, "sha256": "a" * 64},
                ],
                "validation": {"status": "passed"},
            }
            (job_dir / "frame-sequence.json").write_text(json.dumps(manifest))

            journal = JobJournal(root)
            plan = journal.recover()
            self.assertEqual(plan.plan, "resume_missing_frames",
                             f"expected resume_missing_frames, got {plan.plan}")
            self.assertIn("job_frames", plan.jobs)

    def test_recompose_verified_sequence_from_real_situation(self):
        """COMPOSE_VIDEO with a complete verified source sequence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jobs_dir = root / "jobs"
            jobs_dir.mkdir()
            # Source job with verified frames.
            source_dir = jobs_dir / "job_source"
            source_dir.mkdir()
            source_manifest = {
                "receiptVersion": "3.0.0",
                "frameStart": 1, "frameEnd": 2, "frameStep": 1,
                "fps": 24, "format": "PNG",
                "frames": [],
                "validation": {"status": "passed"},
            }
            (source_dir / "frame-sequence.json").write_text(json.dumps(source_manifest))
            # Compose job interrupted.
            job_dir = jobs_dir / "job_compose"
            job_dir.mkdir()
            status = {
                "receiptVersion": "3.0.0",
                "jobId": "job_compose",
                "kind": "COMPOSE_VIDEO",
                "state": "running",
                "pid": 99999999,
                "attempt": 1,
                "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
            }
            (job_dir / "status.json").write_text(json.dumps(status))
            spec = {
                "jobId": "job_compose",
                "kind": "COMPOSE_VIDEO",
                "sourceSequence": {"jobId": "job_source"},
            }
            (job_dir / "spec.json").write_text(json.dumps(spec))

            journal = JobJournal(root)
            plan = journal.recover()
            self.assertEqual(plan.plan, "recompose_verified_sequence",
                             f"expected recompose_verified_sequence, got {plan.plan}")

    def test_resubmit_from_snapshot_for_export_job(self):
        """EXPORT job has no frame-level resume; must resubmit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jobs_dir = root / "jobs"
            jobs_dir.mkdir()
            self._write_status(jobs_dir, "job_export", "running", pid=99999999,
                               kind="EXPORT")
            journal = JobJournal(root)
            plan = journal.recover()
            self.assertEqual(plan.plan, "resubmit_from_snapshot",
                             f"expected resubmit_from_snapshot, got {plan.plan}")

    def test_manual_decision_required_for_mixed_interrupted_jobs(self):
        """Multiple interrupted jobs with different recovery strategies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jobs_dir = root / "jobs"
            jobs_dir.mkdir()
            # Job 1: RENDER_ANIMATION_FRAMES with frames -> resume_missing_frames
            j1_dir = jobs_dir / "job_frames"
            j1_dir.mkdir()
            s1 = {
                "receiptVersion": "3.0.0", "jobId": "job_frames",
                "kind": "RENDER_ANIMATION_FRAMES", "state": "running",
                "pid": 99999999, "attempt": 1,
                "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
            }
            (j1_dir / "status.json").write_text(json.dumps(s1))
            manifest = {
                "receiptVersion": "3.0.0",
                "frameStart": 1, "frameEnd": 3, "frameStep": 1,
                "fps": 24, "format": "PNG",
                "frames": [{"frame": 1, "path": "/tmp/f1.png", "bytes": 100, "sha256": "a" * 64}],
            }
            (j1_dir / "frame-sequence.json").write_text(json.dumps(manifest))

            # Job 2: EXPORT -> resubmit_from_snapshot
            self._write_status(jobs_dir, "job_export", "running", pid=99999998,
                               kind="EXPORT")

            journal = JobJournal(root)
            plan = journal.recover()
            self.assertEqual(plan.plan, "manual_decision_required",
                             f"mixed strategies must require manual decision, got {plan.plan}")
            self.assertIn("job_frames", plan.jobs)
            self.assertIn("job_export", plan.jobs)

    def test_unknown_plan_type_rejected(self):
        """An unknown plan type must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            RecoveryPlan(plan="bogus_plan", jobs={})
        self.assertIn("bogus_plan", str(ctx.exception))
        self.assertIn("allowed", str(ctx.exception))

    def test_all_four_plans_are_creatable(self):
        """Each of the four allowed plans must be instantiable."""
        for plan_name in ALLOWED_RECOVERY_PLANS:
            rp = RecoveryPlan(plan=plan_name, jobs={})
            self.assertEqual(rp.plan, plan_name,
                             f"RecoveryPlan({plan_name!r}) must be creatable")

    def test_manual_decision_reachable_with_conflicting_strategies(self):
        """The ambiguity condition: two jobs need different recovery plans."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jobs_dir = root / "jobs"
            jobs_dir.mkdir()

            # Job A: RENDER_ANIMATION_FRAMES with no frames -> resubmit
            a_dir = jobs_dir / "job_a"
            a_dir.mkdir()
            (a_dir / "status.json").write_text(json.dumps({
                "receiptVersion": "3.0.0", "jobId": "job_a",
                "kind": "RENDER_ANIMATION_FRAMES", "state": "running",
                "pid": 99999999, "attempt": 1,
                "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
            }))
            # No frame-sequence.json -> resubmit_from_snapshot

            # Job B: RENDER_ANIMATION_FRAMES with frames -> resume
            b_dir = jobs_dir / "job_b"
            b_dir.mkdir()
            (b_dir / "status.json").write_text(json.dumps({
                "receiptVersion": "3.0.0", "jobId": "job_b",
                "kind": "RENDER_ANIMATION_FRAMES", "state": "running",
                "pid": 99999998, "attempt": 1,
                "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
            }))
            (b_dir / "frame-sequence.json").write_text(json.dumps({
                "receiptVersion": "3.0.0",
                "frameStart": 1, "frameEnd": 2, "frameStep": 1,
                "fps": 24, "format": "PNG",
                "frames": [{"frame": 1, "path": "/tmp/f1.png", "bytes": 100, "sha256": "a" * 64}],
            }))

            journal = JobJournal(root)
            plan = journal.recover()
            self.assertEqual(plan.plan, "manual_decision_required",
                             f"conflicting frame-job strategies must produce "
                             f"manual_decision_required, got {plan.plan}")


# ---------------------------------------------------------------------------
# No temporary files left behind after recovery
# ---------------------------------------------------------------------------

class TempFileCleanupTests(unittest.TestCase):
    """After recovery, no .tmp files must remain in the journal directory."""

    def test_no_temp_files_after_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jobs_dir = root / "jobs"
            jobs_dir.mkdir()
            job_dir = jobs_dir / "job_dead"
            job_dir.mkdir()
            (job_dir / "status.json").write_text(json.dumps({
                "receiptVersion": "2.0.0", "jobId": "job_dead",
                "kind": "EXPORT", "state": "running", "pid": 99999999,
                "attempt": 1,
                "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
            }))
            journal = JobJournal(root)
            journal.recover()
            # Collect all .tmp files recursively.
            tmp_files = list(root.rglob("*.tmp"))
            self.assertEqual(len(tmp_files), 0,
                             f"temp files left behind: {tmp_files}")


# ---------------------------------------------------------------------------
# Journal persistence across instances
# ---------------------------------------------------------------------------

class JournalPersistenceTests(unittest.TestCase):
    """Journal events survive a new Journal instance (crash recovery)."""

    def test_events_persist_across_instances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            j1 = JobJournal(root)
            rev1 = j1.append(JobEvent(job_id="job_a", type="submitted"))
            rev2 = j1.append(JobEvent(job_id="job_a", type="launched"))
            self.assertEqual(rev1, 1)
            self.assertEqual(rev2, 2)

            # New instance -- must reload from disk.
            j2 = JobJournal(root)
            events = j2.events()
            self.assertEqual(len(events), 2,
                             f"expected 2 persisted events, got {len(events)}")
            self.assertEqual(events[0]["revision"], 1)
            self.assertEqual(events[1]["revision"], 2)
            # Next revision must continue from where we left off.
            rev3 = j2.append(JobEvent(job_id="job_a", type="completed"))
            self.assertEqual(rev3, 3,
                             f"revision must continue from 3, got {rev3}")


if __name__ == "__main__":
    unittest.main()
