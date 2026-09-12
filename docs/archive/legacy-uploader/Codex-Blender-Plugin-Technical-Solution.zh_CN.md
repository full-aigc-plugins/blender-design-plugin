# Codex Blender 插件技术方案

> 历史 clean-room 技术方案。已于 2026-09-12 被
> `docs/superpowers/plans/2026-09-12-codex-blender-integration.md` Revision 3 取代；当前方案
> 完整 vendoring 即梦官方插件，并把两条流程直接委托给官方 operators。

## 1. 技术决策

采用轻量 Codex Skill 层和确定性 Python Bridge，由用户已安装的 Blender 可执行文件启动。不得捆绑 Blender、ffmpeg 或供应商插件源码。

## 2. 目标目录

```text
.codex-plugin/plugin.json
skills/codex-blender-*/SKILL.md
scripts/blender_runner.py
scripts/blender_bridge.py
scripts/media_probe.py
schemas/scene_receipt.schema.json
schemas/artifact_receipt.schema.json
tests/
```

## 3. 执行契约

运行器通过文件描述符或临时文件接收 JSON，并使用 argv 数组调用 Blender。Bridge 在 stdout 只输出一个 JSON 回执；诊断写入 stderr，路径只显示批准范围内的相对标签。

## 4. 预览模式

| 模式 | 来源 | 输出 | Guardrail |
|---|---|---|---|
| 白模 | 当前场景和相机 | Workbench MP4 | 临时覆盖材质并恢复 |
| 材质预览 | 用户材质和纹理 | Workbench MP4 | 不支持的节点转为警告 |
| 已有视频 | 已批准本地文件 | 验证回执 | 不修改场景 |

分辨率预设保持宽高比，`origin` 使用当前场景分辨率。数值限制属于配置，不写死供应商事实；下游可传入 Dreamina profile，本插件只验证该 profile。

## 5. 测试策略

- 用纯 Python 测试校验、状态快照、路径边界和回执。
- 使用 fake `bpy` 做 RED/GREEN 行为测试。
- 用 fixture `.blend` 覆盖相机、无相机、材质、动画和恢复。
- 只有提供明确 Blender 路径时才运行真实冒烟测试。
- 已存在 ffprobe 时才执行媒体验证。

## 6. 失败模型

稳定错误分类：`BLENDER_NOT_FOUND`、`UNSUPPORTED_VERSION`、`PROJECT_NOT_AUTHORIZED`、`CAMERA_NOT_FOUND`、`INVALID_FRAME_RANGE`、`RENDER_FAILED`、`TIMEOUT`、`RESTORE_UNCONFIRMED`、`MEDIA_INVALID`。渲染失败不得自动重试。

## 7. Clean-room 规则

官方 Seedance 上传器只用于观察外部行为和互操作约束。实现必须依据本文档和测试重新编写，不复制源码、字符串、标识、UI 资产或捆绑二进制。
