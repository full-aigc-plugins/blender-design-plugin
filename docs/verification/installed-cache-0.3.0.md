# GitHub Marketplace 0.3.0 缓存验收

本地 `codex-blender@personal` 已卸载，Marketplace 改为 `https://github.com/partme-ai/codex-blender-plugin.git@main`，插件 ID 为 `codex-blender@partme-ai-blender`，安装目录为 `/Users/wandl/.codex/plugins/cache/partme-ai-blender/codex-blender/0.3.0`。

首次新缓存复验时，源码、Marketplace checkout、插件缓存和远端 `main` 均为 `105b105916c9eed381b275ac38f057d15d9018ca`。从缓存目录执行：

- 239 个 Python 测试通过，1 个 Windows-only Named Pipe 测试在 macOS 跳过；
- 分发校验通过；
- Blender 5.2.1 能力目录为 163 tools：136 L3、3 L4、24 L1；
- 持久 PNG、EXR、缺帧恢复和 24 fps MP4 通过；
- 已启用 Rigify 生成 221 个对象。

本地复验产物位于 `/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-cache-0.3.0-105b105/`。证据文档提交后必须再次升级 Marketplace 并重新安装，以最终远端 SHA 作为发布回执，不能停留在该中间 SHA。
