# P8 可靠视频管线验收

## 已验证基线

- Blender 5.2.1 LTS，macOS Apple Silicon。
- 本机 FFmpeg 与 ffprobe。
- 协议继续使用 `codex-blender/v1`；新任务与媒体回执使用 `receiptVersion: 3.0.0`，旧同步导出保持兼容。

## 持久图片序列与恢复

真实场景通过 `RENDER_ANIMATION_FRAMES` 输出 3 帧 320×240 PNG、逐帧字节数和 SHA-256，并绑定提交时的 `.blend` 快照哈希。验收随后故意破坏第 2 帧、删除第 3 帧并把任务标记为中断，再显式调用 `job.resume`。

恢复结果为 `reusedFrames: [1]`、`renderedFrames: [2, 3]`。第 1 帧恢复前后的 SHA-256 和纳秒修改时间保持不变，证明已验证帧没有被覆盖。同一验收还真实渲染并校验了一帧 Blender 5.2 `MULTI_LAYER_IMAGE` OpenEXR。完整证据位于 `/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-frame-pipeline-20260914-v6/`。

同一序列由独立 `COMPOSE_VIDEO` 任务生成 H.264 MP4；ffprobe 验证 320×240、24 fps、精确 3 帧/0.125 秒、可解码、非空并具有独立 SHA-256。源 manifest 在任务提交后发生变化会失败，不会静默合成另一版序列。

## VSE 与合成器

真实 Blender 工程验证以下可编辑结构保存和重开：Scene Strip、三帧 Image Sequence、Text Strip、Wipe、Speed Control、两条声音轨以及由音量关键帧实现的 Sound Crossfade。证据位于 `/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-vse-extended-20260914-v2/`。

合成器验收验证受授权输出目录约束的 File Output、多层 EXR 配置、可复用 CompositorNodeTree，以及 VSE `COMPOSITOR` Modifier 保存重开。实现同时兼容 Blender 5.2 新的 `directory/file_name/file_output_items` API 与旧版 `base_path/file_slots` 结构。证据位于 `/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-compositor-delivery-20260914-v4/`。

## 边界

- 本阶段证明 Blender 渲染器交付持久帧序列和本地确定性 MP4，不接管 Video Factory 的全片计划、字幕工程、旁白、音乐版权或跨镜头编排。
- PNG 路径完成了故障恢复验收；多层 EXR 完成真实单帧渲染、文件头检查、节点配置、保存和重开验收，尚未执行长序列压力测试。
- Windows x64、跨设备模拟一致性和分布式渲染尚未达到 L4。
