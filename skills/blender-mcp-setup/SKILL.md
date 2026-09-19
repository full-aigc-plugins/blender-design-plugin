---
name: blender-mcp-setup
description: "Set up or diagnose the plugin-owned Blender MCP connection when Blender is missing, the Add-on is disabled, Start MCP Server has not been clicked, or no guarded Harness session is discoverable."
---

# Blender MCP Setup

Use this for first use and connection failures. Call `blender_connection_status` before doing
anything else. If it is not connected, run `blender_auto_setup` first — it is the automated
first-run path and requires no manual steps from the user:

1. `blender_auto_setup` discovers the local Blender installation, installs the PartMe Blender MCP
   Add-on into the user's Blender (pulling the latest package from GitHub Releases, falling back
   to the bundled offline package), enables it persistently, and launches Blender with the
   connector auto-started against the default approved output root
   (`~/partme/blender/design-outputs`).
2. When it returns `connected: true`, tell the user in Chinese that Blender 已自动连接 and
   summarize the installed package source and output directory. Setup is done — no manual steps.
3. When it returns `ok: false`, relay `manualHint` verbatim to the user. The two common cases:
   - `stage: discover` — Blender 未安装：给出官网下载链接 https://www.blender.org/download/ ，
     装好后让用户再说一次"连接 Blender"即可。
   - `stage: enable` 且检测到 Blender 正在运行：请用户完全退出 Blender 后重试
     `blender_auto_setup`（自动路径），或改走下面的手动步骤。
4. Only after `blender_auto_setup` fails or the user explicitly prefers manual setup, present the
   illustrated manual path: `blender_getting_started`, then the Chinese setup guide
   [getting-started.zh-CN.md](../../docs/getting-started.zh-CN.md) or the English guide
   [getting-started.md](../../docs/getting-started.md).

Use this manual-fallback summary only in step 4:

> 打开 Blender，在 偏好设置 > 插件 中启用 MCP 插件，然后在 N 面板中点击 Start MCP Server。

The trusted Add-on name is **PartMe Blender MCP** (N-panel category **PartMe MCP**). A separately
installed community Add-on named **MCP for Blender** is not the endpoint for this plugin and must
not be treated as proof that the Blender Harness is connected.

`blender_auto_setup` is the product-approved automation: it may install the Add-on into Blender's
user add-ons directory, enable it persistently, and launch Blender. Any other system change still
requires the user's authorization. Never request or display the private Harness descriptor token.

For error-specific recovery, supported/unsupported boundaries, common misrouting patterns, and
first-use examples, read [setup troubleshooting](references/setup-troubleshooting.md).
