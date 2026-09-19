#!/usr/bin/env python3
"""Fail when either side of the retained Harness compatibility boundary drifts."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _feed(digest, relative: str, data: bytes) -> None:
    # Git may materialize text files with CRLF on Windows. The compatibility
    # boundary tracks source content, not checkout-specific line endings.
    normalized = data.replace(b"\r\n", b"\n")
    digest.update(relative.encode("utf-8") + b"\0" + normalized + b"\0")


def local_tree_hash(root: Path = ROOT) -> str:
    base = root / "scripts" / "harness"
    digest = hashlib.sha256()
    for path in sorted(base.rglob("*.py")):
        _feed(digest, path.relative_to(base).as_posix(), path.read_bytes())
    return digest.hexdigest()


def upstream_tree_hash(root: Path = ROOT) -> tuple[str, str]:
    lock = json.loads((root / "runtime.lock.json").read_text(encoding="utf-8"))
    archive = root / lock["artifacts"]["runtime"]["path"]
    prefix = "src/partme_blender_mcp/harness/"
    digest = hashlib.sha256()
    with zipfile.ZipFile(archive) as bundle:
        for name in sorted(item for item in bundle.namelist()
                           if item.startswith(prefix) and item.endswith(".py")):
            _feed(digest, name[len(prefix):], bundle.read(name))
    return str(lock["version"]), digest.hexdigest()


def validate(root: Path = ROOT) -> list[str]:
    boundary = json.loads((root / "config" / "harness-boundary.json").read_text(encoding="utf-8"))
    version, upstream = upstream_tree_hash(root)
    errors = []
    checks = {
        "pinnedRuntimeVersion": version,
        "localTreeSha256": local_tree_hash(root),
        "upstreamTreeSha256": upstream,
    }
    for key, actual in checks.items():
        if boundary.get(key) != actual:
            errors.append(f"{key} drifted: expected {boundary.get(key)}, got {actual}")
    return errors


if __name__ == "__main__":
    failures = validate()
    if failures:
        raise SystemExit("\n".join(failures))
    print("Harness boundary is unchanged")
