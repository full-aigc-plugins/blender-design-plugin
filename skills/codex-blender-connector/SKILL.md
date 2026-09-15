---
name: codex-blender-connector
description: "Connect Codex to a Blender window that is already open through the optional Codex Blender Connector Add-on."
---

# Connector Blender Session

Use when the user wants to continue the scene already open in Blender. Ask them to install the
generated Connector zip once, enable **Codex Blender Connector** in Preferences, open
`3D View → Sidebar → Codex`, and click **Start MCP Server**. Use `codex-blender-mcp-setup` when
Blender or the connection is missing.

Read the private descriptor only after explicit start. **Revoke Access** invalidates the session.
If Blender switches to an unapproved file, stop mutations and require fresh authorization.
Connector and managed modes use the same commands and receipts.
