# Codex Blender 插件

> 面向 Codex 的安全、可审查 Blender 自动化插件，目前处于设计阶段。

[English](README.md) | [简体中文](README.zh-CN.md)

## 当前状态

仓库当前只包含已确认的架构、技术方案和实施计划，尚无可安装 Codex 插件，也不声称已经完成 Blender 运行兼容性验证。

## 项目定位

`codex-blender` 计划让 Codex 在用户授权范围内检查 `.blend` 项目、准备相机和帧范围、导出 Workbench 或视口预览视频、验证产物，并恢复临时场景设置。它是通用 Blender 适配器，不负责上传到 Dreamina 或其他服务。

```text
Codex 请求
  -> 能力与权限检查
  -> Blender 后台进程 + Python Bridge
  -> 场景检查 / 预览渲染
  -> 媒体验证
  -> 本地 MP4 + 结构化回执
```

## 计划能力

- 发现 Blender 可执行文件与版本，不自动安装。
- 只读检查场景、相机、动画、材质和输出设置。
- 支持白模、材质预览和已有视频三种工作流。
- 通过 Workbench 导出预览，并保证恢复场景状态。
- 校验分辨率、帧范围、帧率、编码、时长和文件大小。
- 输出可被 `dreamina-3d` 消费的稳定回执。

## 安全边界

- 不自动安装 Blender、插件、ffmpeg 或 Python 包。
- 不负责远程上传、浏览器控制或付费生成。
- 未经明确授权，不执行 `.blend` 内的不可信脚本。
- 临时场景修改必须记录，并在 `finally` 路径恢复。
- 输出路径必须位于用户批准目录内。

## 文档

- [Architecture](docs/Codex-Blender-Plugin-Architecture.md)
- [架构文档](docs/Codex-Blender-Plugin-Architecture.zh_CN.md)
- [Technical solution](docs/Codex-Blender-Plugin-Technical-Solution.md)
- [技术方案](docs/Codex-Blender-Plugin-Technical-Solution.zh_CN.md)
- [设计规格](docs/superpowers/specs/2026-09-11-codex-blender-plugin-design.md)
- [实施计划](docs/superpowers/plans/2026-09-11-codex-blender-plugin-implementation.md)

## 验收目标

只有单元测试、场景 fixture 测试、媒体验证、恢复测试、插件校验，以及经用户明确授权的 Blender 运行冒烟测试全部通过，首版实现才算完成。

## 许可证

许可证选择和初始 `LICENSE` 文件属于实施任务；当前仅设计仓库，不构成许可证授权。
