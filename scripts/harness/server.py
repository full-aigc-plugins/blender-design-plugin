"""Composition of transport, main-thread execution, and Harness session."""

from __future__ import annotations

import json
import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

from .main_thread import MainThreadExecutor
from .runtime import create_session
from .snapshot import BlenderCheckpointStore
from .transport import Endpoint, JsonLineServer, choose_endpoint
from .transaction import TransactionManager


@dataclass
class HarnessRuntime:
    endpoint: Endpoint
    descriptor_path: Path
    transport: JsonLineServer
    executor: MainThreadExecutor
    bpy_module: object

    def close(self) -> None:
        self.transport.close()
        try:
            self.bpy_module.app.timers.unregister(self.executor.blender_timer_callback)
        except Exception:
            pass
        try:
            self.descriptor_path.unlink()
        except FileNotFoundError:
            pass


def start_harness(
    bpy_module,
    *,
    session_id: str,
    runtime_dir: Path,
    endpoint: Endpoint | None = None,
    approved_output_root: Path | None = None,
    approved_asset_roots=(),
) -> HarnessRuntime:
    runtime_dir = Path(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(runtime_dir, 0o700)
    token = secrets.token_urlsafe(32)
    checkpoint_store = BlenderCheckpointStore(bpy_module, runtime_dir / "checkpoints")
    transactions = TransactionManager(
        capture=checkpoint_store.capture,
        restore=checkpoint_store.restore,
        journal_path=runtime_dir / "recovery.json",
    )
    session = create_session(
        bpy_module,
        session_id,
        approved_output_root=approved_output_root or runtime_dir / "outputs",
        approved_asset_roots=approved_asset_roots,
        transactions=transactions,
    )
    executor = MainThreadExecutor()
    selected = endpoint or choose_endpoint(sys.platform, session_id=session_id, runtime_dir=str(runtime_dir))
    transport = JsonLineServer(
        selected,
        token=token,
        handle=lambda payload: executor.submit(lambda: session.handle(payload), timeout=30),
    )
    actual_endpoint = transport.start()
    bpy_module.app.timers.register(executor.blender_timer_callback, first_interval=0.01, persistent=True)

    descriptor_path = runtime_dir / f"{session_id}.json"
    address = list(actual_endpoint.address) if isinstance(actual_endpoint.address, tuple) else actual_endpoint.address
    descriptor_path.write_text(
        json.dumps(
            {
                "protocolVersion": "codex-blender/v1",
                "sessionId": session_id,
                "transport": actual_endpoint.kind,
                "address": address,
                "token": token,
                "pid": os.getpid(),
                "outputRoot": str((approved_output_root or runtime_dir / "outputs").resolve()),
                "assetRoots": [str(Path(value).resolve()) for value in approved_asset_roots],
            },
            sort_keys=True,
        )
    )
    os.chmod(descriptor_path, 0o600)
    return HarnessRuntime(actual_endpoint, descriptor_path, transport, executor, bpy_module)
