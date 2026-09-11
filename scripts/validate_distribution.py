#!/usr/bin/env python3
"""Validate that the codex-blender distribution is structurally complete.

Checks:
  - .codex-plugin/plugin.json exists and has required fields
  - plugin.json declares a license field
  - Schema files exist in schemas/

Does NOT require a LICENSE file to exist on disk (that is a human legal decision).
"""

import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

    if errors:
        print("\n".join(f"ERROR: {e}" for e in errors))
        return 1

    print("Distribution validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
