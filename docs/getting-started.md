# Install and connect Codex Blender

## No Blender yet? [Download the installer](https://www.blender.org/download/)

Open Blender, enable the MCP Add-on in **Preferences > Add-ons**, then press `N` in the 3D View and
click **Start MCP Server**.

The trusted Add-on for this plugin is **Codex Blender Connector**. A separately installed community
Add-on named **MCP for Blender** is not evidence that the guarded Codex Blender Harness is connected.

## 1. Open Preferences

Choose **Edit > Preferences**.

![Open Blender Preferences](../assets/getting-started/blender-preferences-menu.png)

## 2. Install and enable the Add-on

Choose **Add-ons > Install from Disk**, select `codex-blender-connector.zip`, and enable
**Codex Blender Connector**. The screenshot demonstrates the Add-ons location; its community Add-on
name is illustrative and is not the trusted Codex Blender endpoint.

![Enable a Blender Add-on](../assets/getting-started/blender-enable-mcp-addon.png)

## 3. Start MCP Server

Return to the 3D View, press `N`, open **Codex**, select the approved output and asset directories,
and click **Start MCP Server**. Setup is complete only when `blender_connection_status` returns
`connected: true`.

The MCP adapter runs from the plugin's `.mcp.json`, exposes registered Harness commands as MCP tools,
and retains the Harness token, revision, transaction, authorization, and recovery boundaries.
