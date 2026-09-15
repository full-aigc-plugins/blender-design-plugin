---
name: codex-blender-connector
description: "Connect Codex to an already-open Blender window through the pinned PartMe Blender MCP Add-on."
---

# Connector Blender Session

Use when the user wants to continue the scene already open in Blender. Ask them to install the
generated Add-on zip once, enable **PartMe Blender MCP** in Preferences, open
`3D View → Sidebar → PartMe MCP`, and click **Start MCP Server**. Use `codex-blender-mcp-setup` when
Blender or the connection is missing.

Read the private descriptor only after explicit start. **Revoke Access** invalidates the session.
If Blender switches to an unapproved file, stop mutations and require fresh authorization.
Connector and managed modes use the same commands and receipts.
