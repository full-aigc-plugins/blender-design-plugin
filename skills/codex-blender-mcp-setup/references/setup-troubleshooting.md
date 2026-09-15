# Codex Blender MCP setup troubleshooting

## Decision table

| Observed result | Meaning | User-facing next action |
|---|---|---|
| `blenderInstalled: false` | No supported Blender executable was found | Give the official download link; do not install automatically |
| `BLENDER_NOT_CONNECTED` | No live guarded Harness answered | Enable **Codex Blender Connector**, then click **Start MCP Server** |
| `UNSAFE_DESCRIPTOR` | Descriptor is a symlink or has broad permissions | Stop; reinstall or repair the trusted Connector instead of bypassing the check |
| `AMBIGUOUS_SESSION` | More than one Blender Harness is active | Ask which Blender window to control; bind its exact descriptor through approved configuration |
| `AUTHORIZATION_REQUIRED` | A gated operation lacks action-bound approval | Explain the exact operation and obtain confirmation at action time |
| `STALE_SCENE_REVISION` | Blender changed after the last observation | Reinspect, use the returned revision, and start a fresh transaction |

Never reduce these failures to “MCP broken.” State what is missing and the one action that resolves it.

## Boundaries

The setup workflow can:

- Detect Blender in standard locations.
- Show local illustrated installation guidance.
- Verify one live private Harness endpoint without revealing its token.
- Distinguish the trusted Connector from a community `MCP for Blender` Add-on.

It needs user action or authorization to:

- Install Blender or the Connector Add-on.
- Enable an Add-on or change Blender Preferences.
- Select between multiple open Blender sessions.
- Approve deletion, overwrite, expert Python, final export, or another gated command.

It does not:

- Treat a third-party TCP listener as the trusted Harness.
- Download community Add-ons, assets, or extensions silently.
- Collect, display, or copy the private descriptor token.
- Prove modeling, rendering, or export quality merely because MCP connected.

## Common anti-patterns

1. **“MCP for Blender is enabled, therefore Codex Blender is connected.”**  
   Correct by checking `blender_connection_status` and naming **Codex Blender Connector**.
2. **“Start a fixed port and accept arbitrary Python.”**  
   Correct by retaining the private Harness descriptor, token, closed schemas, and gated expert command.
3. **“Retry every descriptor until one works.”**  
   Correct by stopping on multiple live sessions so the wrong project is never edited.
4. **“Connection succeeded, so the requested scene is complete.”**  
   Correct by routing to the relevant production Skill and its visual/delivery validation.

## First-use prompts

- “我还没有安装 Blender，告诉我官方下载地址和安装后的第一步。”
- “Blender 已打开，帮我检查 Codex Blender MCP 是否连接。”
- “我看到 MCP for Blender，但 Codex 仍然不能操作场景，帮我区分两个插件。”

## FAQ

**Why not use the community Add-on already visible in Blender?**  
It is a separate trust boundary and may expose arbitrary Python or telemetry. This plugin uses its own guarded Harness.

**Does installing the Codex plugin install Blender?**  
No. Blender is a separate application downloaded from the official Blender website.

**Must every workflow install the Blender Add-on?**  
Managed mode can temporarily load the Harness. Connecting an already-open Blender window uses the Add-on.

**Why does the MCP server start from `.mcp.json` automatically but Blender still says disconnected?**  
The stdio adapter and the Blender Harness are two processes. The adapter remains available to show setup even before Blender connects.

**What if two Blender windows are open?**  
Do not choose silently. Identify the intended window and bind its exact private descriptor.

**May the user change the scene manually after connecting?**  
Yes. Pause/take over, then resume and reinspect; old transactions and approvals are invalidated.

**Does connection authorize exports or deletion?**  
No. Gated operations still require the existing action-bound authorization and output policy.

**What should be delivered after setup succeeds?**  
Only connection evidence. Modeling, preview, validation, and export receipts belong to their respective Skills.
