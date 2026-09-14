# Windows L4 与 Rigify 安装验收

## Windows x64

`.github/workflows/windows-l4.yml` 在真实 `windows-2025` Runner 下载 Blender 官方 5.2.1 x64 ZIP，并以官方 SHA-256 `0e631dad7d0cad6d5d18abdd2e2550f6c0213215334eda00ddbd3d22b96ecb2c` 校验。流程运行完整 Python 回归、分发校验、Connector 打包、持久帧故障恢复、FFmpeg 合成和 Rigify 生成。

Windows L4 已由 [GitHub Actions run 34798159616](https://github.com/partme-ai/codex-blender-plugin/actions/runs/34798159616) 验证。远端 artifact 下载并复核后，补帧恢复和 Rigify 报告均为 `productionAcceptance: true`。本地证据镜像位于 `/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-windows-l4-34798159616/`。

该证据证明 Windows Server 2025 x64、Blender 5.2.1、Python 3.13、真实 Named Pipe 认证往返、Cycles CPU 后台渲染、缺帧恢复、多层 EXR、FFmpeg/ffprobe、Rigify 和 Connector 打包兼容。GitHub Runner 没有交互桌面，因此不把前台 Blender UI/人工接管标成 L4。

## Rigify 自动安装边界

Blender 5.2 官方手册声明 Rigify 随 Blender 捆绑，许可证为 GPL。`rig.rigify_install` 是 gated 命令，只处理固定目标 Rigify：

1. 先检查 Rigify 是否已经启用。
2. 检测到捆绑模块时直接启用，可按请求保存 Blender 用户偏好，不访问网络。
3. 仅当模块不存在且调用者明确设置 `allowDownload: true` 时，检查 Blender 在线访问和官方 `extensions.blender.org` repository。
4. 下载路径只允许固定 `pkg_id: rigify`，不接受任意 URL、repository 或包名。
5. 安装后再次检查 `pose.rigify_generate`，再允许 `rig.rigify_generate`。

macOS Blender 5.2.1 验收采用 `bundled-enable`，保存偏好后由 Human Meta-Rig 生成 221 个 Rigify 对象，没有下载。证据位于 `/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-rigify-install-20260914-v2/`。
