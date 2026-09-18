---
description: Blender 首次安装向导：Add-on、连接模式与 harness 预检
argument-hint: "[要处理的项：addon|connector|managed|diagnose]"
---

按 `blender-mcp-setup` 技能完成一次性安装与连接：

1. **Add-on**：打包/安装 PartMe Blender MCP Add-on（Edit → Preferences → Add-ons），
   3D 视图按 N 启动 **Start MCP Server**——这是唯一需要手动做的 Blender 侧步骤。
2. **连接模式**：选择 managed（受控，默认）或 connector（前台连接已开的 Blender 窗口）。
3. **预检**：确认 Blender 版本、harness 可达、ffprobe 就绪；异常按技能的诊断段处理。

完成后用 `/blender-inspect` 验证连通，再进 `/blender-design` 或 `/blender-previs`。
