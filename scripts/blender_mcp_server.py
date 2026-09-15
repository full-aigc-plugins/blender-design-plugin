#!/usr/bin/env python3
"""Start the plugin-owned Codex Blender MCP stdio adapter."""

from __future__ import annotations

import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.harness.mcp_adapter import serve_stdio


if __name__ == "__main__":
    raise SystemExit(serve_stdio())
