"""Real restart recovery acceptance: SIGKILL a worker process and verify recovery.

This script runs under Blender --background.  It:
  1. Creates a job that will run as a real Blender subprocess.
  2. Kills the subprocess with SIGKILL while it is mid-run.
  3. Verifies the journal recovers the job as ``interrupted``.
  4. Verifies the RecoveryPlan is one of the four allowed types.
  5. Asserts no .tmp files are left behind.
  6. Writes a JSON report and exits 0 on success, non-zero on failure.

Usage:
  cd $WT && "/Applications/Blender.app/Contents/MacOS/Blender" \\
    --background --factory-startup --python-exit-code 1 \\
    --python tests/runtime/restart_recovery_acceptance.py -- /tmp/jr_out
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# We do NOT import bpy-dependent modules here; we only need the journal.
from scripts.harness.job_journal import (
    ALLOWED_RECOVERY_PLANS,
    JobEvent,
    JobJournal,
)

assert "--" in sys.argv, "pass output directory after --"
output = Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True)

# ---------------------------------------------------------------------------
# Report collector
# ---------------------------------------------------------------------------

report = {
    "test": "restart_recovery_acceptance",
    "root": str(output),
    "steps": [],
    "errors": [],
}
_exit_code = 0


def fail(msg):
    global _exit_code
    report["errors"].append(msg)
    _exit_code = 1


def step(name, **kw):
    report["steps"].append({"name": name, **kw})


# ---------------------------------------------------------------------------
# 1. Set up a job directory that looks like a running job.
# ---------------------------------------------------------------------------

jobs_dir = output / "jobs"
jobs_dir.mkdir(parents=True, exist_ok=True)
job_id = "job_rr_kill"
job_dir = jobs_dir / job_id
job_dir.mkdir(exist_ok=True)

# Write spec.json (minimal).
spec = {
    "jobId": job_id,
    "kind": "RENDER_ANIMATION_FRAMES",
    "format": "",
    "parameters": {
        "frameStart": 1, "frameEnd": 100, "frameStep": 1,
        "frames": list(range(1, 101)),
        "width": 64, "height": 48,
        "imageFormat": "PNG", "extension": "png",
        "colorMode": "RGBA", "colorDepth": "8",
        "includeAudio": False,
    },
    "snapshot": {
        "path": "/dev/null",
        "sha256": "a" * 64,
        "sceneFile": "",
    },
}
(job_dir / "spec.json").write_text(json.dumps(spec, indent=2))

# ---------------------------------------------------------------------------
# 2. Start a real subprocess that will run for a while (sleep loop).
# ---------------------------------------------------------------------------

# We use a Python subprocess that writes "running" status, then sleeps.
# We will SIGKILL it while it sleeps.
worker_script = job_dir / "_slow_worker.py"
worker_script.write_text(textwrap := """
import json, os, sys, time
from pathlib import Path

task_dir = Path(sys.argv[1])
status_path = task_dir / "status.json"
status = {
    "receiptVersion": "3.0.0",
    "jobId": "job_rr_kill",
    "kind": "RENDER_ANIMATION_FRAMES",
    "state": "running",
    "pid": os.getpid(),
    "attempt": 1,
    "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
}
status_path.write_text(json.dumps(status, indent=2))
# Simulate long-running work.
time.sleep(300)
""", encoding="utf-8")

step("setup", job_id=job_id, job_dir=str(job_dir))

# Write initial status as "queued" so the journal sees an indeterminate state.
initial_status = {
    "receiptVersion": "3.0.0",
    "jobId": job_id,
    "kind": "RENDER_ANIMATION_FRAMES",
    "state": "queued",
    "attempt": 1,
    "snapshot": {"path": "/dev/null", "sha256": "a" * 64, "sceneFile": ""},
}
(job_dir / "status.json").write_text(json.dumps(initial_status, indent=2))

# Launch the worker subprocess.
proc = subprocess.Popen(
    [sys.executable, str(worker_script), str(job_dir)],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
step("worker_launched", pid=proc.pid)

# Wait for the worker to write its "running" status.
status_path = job_dir / "status.json"
deadline = time.monotonic() + 10
while time.monotonic() < deadline:
    try:
        s = json.loads(status_path.read_text(encoding="utf-8"))
        if s.get("state") == "running" and s.get("pid") == proc.pid:
            break
    except (OSError, json.JSONDecodeError):
        pass
    time.sleep(0.1)
else:
    fail("worker did not write running status within 10 seconds")

step("worker_running", pid=proc.pid, status_state=s.get("state"))

# ---------------------------------------------------------------------------
# 3. SIGKILL the worker.
# ---------------------------------------------------------------------------

os.kill(proc.pid, signal.SIGKILL)
wait_result = proc.wait(timeout=5)
# On Unix, a SIGKILL'd process has returncode = -9 (negative signal number).
# os.wait may return (pid, status) or just the returncode depending on API.
# proc.wait() returns the returncode.
step("worker_killed", pid=proc.pid, returncode=wait_result,
     signal_name="SIGKILL", signal_number=signal.SIGKILL)

# Verify the process is actually dead.
try:
    os.kill(proc.pid, 0)
    fail(f"process {proc.pid} is still alive after SIGKILL")
except OSError:
    pass  # Expected: process is dead.

step("process_confirmed_dead", pid=proc.pid)

# ---------------------------------------------------------------------------
# 4. Recover via the journal.
# ---------------------------------------------------------------------------

journal = JobJournal(output)
plan = journal.recover()

step("recovery_complete", plan=plan.plan, jobs=list(plan.jobs.keys()))

# Verify the plan is one of the four allowed.
if plan.plan not in ALLOWED_RECOVERY_PLANS:
    fail(f"plan {plan.plan!r} is not in allowed set {sorted(ALLOWED_RECOVERY_PLANS)}")

# Read back the status -- must be interrupted.
recovered_status = json.loads(status_path.read_text(encoding="utf-8"))
if recovered_status["state"] != "interrupted":
    fail(f"expected state 'interrupted', got {recovered_status['state']!r}")

step("status_verified", state=recovered_status["state"],
     expected="interrupted",
     matches=recovered_status["state"] == "interrupted")

# For a RENDER_ANIMATION_FRAMES job with no verified frames, the plan
# should be resubmit_from_snapshot.
if plan.plan != "resubmit_from_snapshot":
    fail(f"expected plan 'resubmit_from_snapshot' (no frames on disk), got {plan.plan!r}")

step("plan_verified", expected="resubmit_from_snapshot", actual=plan.plan,
     matches=plan.plan == "resubmit_from_snapshot")

# ---------------------------------------------------------------------------
# 5. Assert no .tmp files left behind.
# ---------------------------------------------------------------------------

tmp_files = list(output.rglob("*.tmp"))
if len(tmp_files) != 0:
    fail(f"temp files left behind after recovery: {[str(f) for f in tmp_files]}")

step("no_temp_files", tmp_count=len(tmp_files), clean=len(tmp_files) == 0)

# ---------------------------------------------------------------------------
# 6. Write report and exit.
# ---------------------------------------------------------------------------

report["exitCode"] = _exit_code
report["summary"] = {
    "killedPid": proc.pid,
    "killedSignal": signal.SIGKILL,
    "killedReturncode": wait_result,
    "recoveredState": recovered_status["state"],
    "recoveryPlan": plan.plan,
    "tempFilesLeft": len(tmp_files),
    "errors": len(report["errors"]),
}

report_path = output / "restart-recovery-acceptance.json"
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(f"RESTART_RECOVERY_ACCEPTANCE={json.dumps(report)}")

# Exit code.
if _exit_code != 0:
    print(f"FAILED: {report['errors']}", file=sys.stderr)
    sys.exit(_exit_code)
print("PASSED: restart recovery acceptance")
