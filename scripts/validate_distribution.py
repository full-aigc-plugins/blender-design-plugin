#!/usr/bin/env python3
"""Validate that the codex-blender distribution is structurally complete.

Checks:
  - .codex-plugin/plugin.json exists and has required fields
  - plugin.json declares a license field
  - Schema files exist in schemas/
  - Four Skills exist in skills/
  - UPSTREAM.md exists and records provenance
  - No committed binaries above a size threshold
  - No symlinks in the tree
  - No secret patterns in tracked files

Does NOT require a LICENSE file to exist on disk (that is a human legal decision).
"""

import json
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_EXPECTED_SKILLS = [
    "codex-blender-use",
    "codex-blender-inspect",
    "codex-blender-export-preview",
    "codex-blender-link",
]

_MAX_BINARY_BYTES = 1024 * 1024  # 1 MiB

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub personal access token
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI API key
]


def _is_binary(path):
    """Heuristic: file has a known binary extension."""
    binary_exts = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mov", ".webm", ".avi",
                   ".exe", ".dll", ".so", ".dylib", ".bin", ".zip", ".tar", ".gz",
                   ".woff", ".woff2", ".ttf", ".eot"}
    _, ext = os.path.splitext(path)
    return ext.lower() in binary_exts


def main() -> int:
    errors: list[str] = []

    # --- plugin.json ---
    plugin_path = os.path.join(_REPO_ROOT, ".codex-plugin", "plugin.json")
    if not os.path.isfile(plugin_path):
        errors.append("Missing .codex-plugin/plugin.json")
        print("\n".join(f"ERROR: {e}" for e in errors))
        return 1

    with open(plugin_path) as f:
        plugin = json.load(f)

    required_fields = ["id", "version", "name", "description", "license", "skills", "entryPoint"]
    for field in required_fields:
        if field not in plugin:
            errors.append(f"plugin.json missing required field: {field}")

    # --- schemas ---
    for schema_name in ("scene_receipt", "artifact_receipt"):
        schema_path = os.path.join(_REPO_ROOT, "schemas", f"{schema_name}.schema.json")
        if not os.path.isfile(schema_path):
            errors.append(f"Missing schema file: schemas/{schema_name}.schema.json")

    # --- Skills ---
    skills_dir = os.path.join(_REPO_ROOT, "skills")
    for skill_name in _EXPECTED_SKILLS:
        skill_path = os.path.join(skills_dir, skill_name, "SKILL.md")
        if not os.path.isfile(skill_path):
            errors.append(f"Missing Skill: skills/{skill_name}/SKILL.md")

    # --- UPSTREAM.md provenance ---
    upstream_path = os.path.join(_REPO_ROOT, "vendor", "jimeng_blender_uploader", "UPSTREAM.md")
    if not os.path.isfile(upstream_path):
        errors.append("Missing vendor/jimeng_blender_uploader/UPSTREAM.md (provenance record)")
    else:
        with open(upstream_path) as f:
            content = f.read()
        # Check that it records at least the five expected hashes
        for name in ("dcc_config.py", "upload_bridge.py", "settings.py", "variant.py", "viewport_render.py"):
            if name not in content:
                errors.append(f"UPSTREAM.md missing record for {name}")

    # --- No committed binaries above threshold ---
    for root, dirs, files in os.walk(_REPO_ROOT):
        # Skip .git and .superpowers
        dirs[:] = [d for d in dirs if d not in (".git", ".superpowers", "__pycache__")]
        for name in files:
            path = os.path.join(root, name)
            if _is_binary(path):
                size = os.path.getsize(path)
                if size > _MAX_BINARY_BYTES:
                    rel = os.path.relpath(path, _REPO_ROOT)
                    errors.append(f"Binary file exceeds {_MAX_BINARY_BYTES} bytes: {rel} ({size} bytes)")

    # --- No symlinks ---
    for root, dirs, files in os.walk(_REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", ".superpowers", "__pycache__")]
        for name in files + dirs:
            path = os.path.join(root, name)
            if os.path.islink(path):
                rel = os.path.relpath(path, _REPO_ROOT)
                errors.append(f"Symlink found: {rel}")

    # --- Secret patterns ---
    for root, dirs, files in os.walk(_REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", ".superpowers", "__pycache__", "node_modules")]
        for name in files:
            if not name.endswith((".py", ".json", ".md", ".txt", ".yml", ".yaml")):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, errors="replace") as f:
                    content = f.read()
            except Exception:
                continue
            for pattern in _SECRET_PATTERNS:
                if pattern.search(content):
                    rel = os.path.relpath(path, _REPO_ROOT)
                    errors.append(f"Possible secret in {rel}: {pattern.pattern[:50]}...")

    if errors:
        print("\n".join(f"ERROR: {e}" for e in errors))
        return 1

    print("Distribution validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
