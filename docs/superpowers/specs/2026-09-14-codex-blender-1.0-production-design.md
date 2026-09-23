# Codex Blender 1.0 生产版设计规格

> 本规格是 `docs/superpowers/plans/2026-09-14-codex-blender-1.0-production.md` 的权威依据。
> 计划是该规格的论证；冲突时以本规格为准。**Status:** 目标规格（target spec），非已实现状态。

## 1. 目标

将 `codex-blender-plugin` 从 0.3.0 提升为 **1.0 生产版本**，在 **Blender 4.2–5.2**、
**macOS arm64** 与 **Windows x64** 上提供可验证的生产能力，并通过签名发布对外提供。

## 2. 范围

### 在范围内

- 生产 Profile：以证据分级（L1–L4）约束哪些命令可进入生产目录
- Blender 4.2–5.2 集中版本适配层（compat adapter）
- 制作领域闭环：UV、重拓扑、角色变形/动画、Hair/Simulation/Grease Pencil、Material/Compositor/VSE
- 可靠性与可移植性：依赖清单、工程打包、资源预估、双任务调度、原子 Journal、重启恢复
- 安全与可观测性：传输/路径/子进程加固、本地脱敏支持包
- 桌面认证、升级回滚、1.0 发布门禁与供应链（SBOM、checksum、Sigstore provenance）

### 明确不在范围内（非目标）

- 即梦生成、编剧、计费、长剧情、跨插件制片
- 任意 Python 执行进入生产 Profile（`advanced.execute_python` 固定为 `expert`，不计生产覆盖）
- 任意 URL / 仓库 / 包名的扩展安装（Rigify 是固定白名单扩展）
- 遥测上传（只生成本地脱敏诊断包）

## 3. 固定事实（不得由实现自行选择）

| 项 | 固定值 |
| --- | --- |
| 正式 Blender 版本 | 4.2.23、4.3.2、4.4.3、4.5.13、5.0.1、5.1.2、5.2.1 |
| 正式平台 | macOS arm64、Windows x64 |
| Linux | 仅 experimental headless |
| 单项目时长上限 | 600 秒 |
| 分辨率上限 | 3840×2160 |
| 并发 active 后台任务 | 最多 2 个 |
| Job log 轮转 | 50 MiB × 5 |
| 磁盘保留 | `max(卷容量 20%, 20GB)` |
| Blender 包来源 | <https://download.blender.org/release/> 的官方 `.sha256` |
| 契约兼容 | 保持 v1 请求 Envelope；v1–v3 回执兼容；新增生产回执用 v4 |

## 4. 证据分级与门禁

成熟度以**真实证据**分级，禁止用文档宣称替代运行证据：

- **L1** — 已注册但无运行证据。
- **L3** — 有运行证据（真实 Blender 执行）。
- **L4** — 在 L3 之上另有**恢复**与**兼容**证据（例如断电/取消后恢复、跨版本或跨平台一致）。

生产 Profile 的门禁：

- 生产目录中 **L1 = 0 且 L2 = 0**；所有 production 命令 ≥ L3。
- 关键保存/导出/恢复/安装/迁移路径必须 **≥ L4**。
- `evidence` 中声明的路径**不存在时 Validator 必须失败**（禁止悬空证据）。
- optional 能力（如 Connector 官方上传器）**不得阻塞**核心 ready 判定。

## 5. 度量口径

- **Managed 与 Connector 必须分别统计，禁止合并成单一命令总数。**
- 所有对外数字（README、验收文档）**必须来自运行时生成结果**，不得手工维护。
- 生成接口：`generate_coverage_summary(runtime_mode: str) -> dict`。
- 同时记录：当前源码 / 安装缓存 / 远端 SHA，以及 CI 与 Windows L4 对应 commit。

## 6. 关键不变式

1. **离线可用**：核心流程必须在 Blender + FFmpeg 的离线环境工作。
2. **可编辑性**：重拓扑等产物必须保持可编辑；不得把 Voxel/Quadriflow 自动结果宣传为专业手工重拓扑。
3. **原子性**：spec/status/manifest 写入使用同目录临时文件 + flush + fsync + atomic replace；revision 单调递增；事件只追加。
4. **恢复有界**：不确定的 running 任务恢复为 interrupted；RecoveryPlan 只允许
   `resume_missing_frames`、`recompose_verified_sequence`、`resubmit_from_snapshot`、`manual_decision_required`。
5. **不抢占**：优先级只调整 queued 顺序，不抢占 running；超资源限制时不保存快照、不启动进程。
6. **路径安全**：打开文件后再次验证路径（防 check/use 替换）；Proxy 等输出路径必须在授权目录内。
7. **子进程**：终止整个进程组 / Windows Job Object；不留下 Blender/FFmpeg 残留进程。
8. **默认拒绝**：不接受任意 node/operator 字符串；FFmpeg 只允许本地 file、pipe、concat。

## 7. 验收权威

“完全生产就绪”的宣称**只在** `docs/superpowers/plans/2026-09-14-codex-blender-1.0-production.md`
的「完成定义」全部满足时成立 —— 包括七版本 × 双平台前后台、10 分钟 4K、双任务并发、
崩溃/取消/磁盘不足/重启恢复、异机重开、安全无 P0/P1、v1–v4 契约、七类 Golden Project 的
技术与**人工视觉**验收，以及 Release/SBOM/checksum/签名 provenance 与
GitHub/tag/Marketplace/缓存/artifact 的 SHA 一致。

**任何单项不满足即不得声称 1.0 完成。**

## 8. 开发纪律

- 在 `feat/blender-1.0-production` worktree 实施，**不得直接在 `main` 开发**。
- 每项任务 RED → GREEN → REVIEW → COMMIT。
- 无法在当前环境运行的验收必须显式记录为未运行及其原因，**不得以文档或推断替代**。
