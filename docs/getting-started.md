# Install and connect Blender Design

## Automatic connection (recommended)

After installing Blender and this plugin, just tell your AI agent: **"connect Blender"**. It calls
`blender_auto_setup`, which discovers your Blender installation, installs the **PartMe Blender MCP**
Add-on (pulling the latest package from GitHub Releases with a bundled offline fallback), enables it
persistently, launches Blender, and auto-starts the connector. The default approved output directory
is `~/partme/blender/design-outputs` (override with the `outputRoot` argument).

## Manual steps

> ### No Blender yet? [Download the installer](https://www.blender.org/download/)
>
> Open Blender, enable the MCP Add-on in **Preferences > Add-ons**, then press `N` in the 3D View and
> click **Start MCP Server**.

The trusted Add-on for this plugin is **PartMe Blender MCP**. A separately installed community
Add-on named **MCP for Blender** is not evidence that the guarded Blender Design Harness is connected.

## 1. Open Preferences

Choose **Edit > Preferences**.

![Open Blender Preferences](../assets/getting-started/blender-preferences-menu.png)

## 2. Install and enable the Add-on

Choose **Add-ons > Install from Disk**, select `partme-blender-mcp-addon-0.2.0.zip`, and enable
**PartMe Blender MCP**. The screenshot demonstrates the Add-ons location; its community Add-on
name is illustrative and is not the trusted Blender Design endpoint.

![Enable a Blender Add-on](../assets/getting-started/blender-enable-mcp-addon.png)

## 3. Start MCP Server

Return to the 3D View, press `N`, open **PartMe MCP**, select the approved output and asset directories,
and click **Start MCP Server**. Setup is complete only when `blender_connection_status` returns
`connected: true`.

The MCP adapter runs from the plugin's `.mcp.json`, exposes registered Harness commands as MCP tools,
and retains the Harness token, revision, transaction, authorization, and recovery boundaries.
