# Codex Blender 插件技术方案

## 技术选型

| 选择 | 理由 |
|---|---|
| 只用 Blender Python API，不引入 C++ 或外部 DCC SDK | 插件必须能跑在用户自己的 Blender 5.2.1 LTS 里，不需要构建步骤 |
| macOS 用 Unix Domain Socket，Windows 用 Named Pipe，并保留令牌化环回 TCP 回退 | 本地传输既不暴露端口，又能覆盖两个发布门禁平台 |
| 版本化协议上的闭合 JSON 命令文档 | Codex 可以在派发前校验请求，未知命令关闭式失败 |
| 单一命令注册表，由两种运行模式共用 | 托管模式与 Connector 模式无法漂移成两套能力集 |
| Python 3 `unittest` | 无第三方测试依赖，测试能在运行插件的同一环境里跑 |
| `vendor/` 下供应商视口渲染器 | 把官方上传器的渲染行为作为隔离研究材料保留，而不是重新实现 |
| 通过 ffprobe 独立探测媒体 | 文件存在不等于文件正确 |

## Blender 探测与启动

托管模式解析 Blender 可执行文件，然后用临时引导脚本启动它（`managed_launcher.py` 调用 `managed_bootstrap.py`），不写入任何偏好设置或插件。Connector 模式完全不启动：`connector/codex_blender_connector/` 中的插件在已经运行的 Blender 内注册，并宣告同一套协议。

两种模式随后收敛到同一套发现握手：打开传输、交换会话密钥、协商 `codex-blender/v1`，并从命令注册表发布能力清单。`launch_harness.py` 与 `harness_cli.py` 是 Codex 使用的入口。

## 命令与 Schema 契约

请求是闭合的 JSON 文档。每个请求携带 `protocolVersion`（`codex-blender/v1`）、`sessionId`、唯一 `requestId`、`transactionId`、已注册的 `command`、闭合的 `arguments` 对象，并且对每一次修改都携带 `expectedSceneRevision`。受门禁操作额外携带授权声明。

响应携带请求状态、新的场景修订号、变更对象、告警、快照 ID 与结构化错误信息。重复的 `requestId` 返回先前响应，不重复执行。

`schemas/` 下的 JSON Schema 是该契约可机器校验的另一半：

```text
schemas/artifact_receipt.schema.json
schemas/command.schema.json
schemas/frame_sequence_receipt.schema.json
schemas/milestone_receipt.schema.json
schemas/render_plan.schema.json
schemas/response.schema.json
schemas/video_artifact_receipt.schema.json
```

## 目录结构

```text
.codex-plugin/plugin.json     plugin manifest (id codex-blender)
bin/                          executable adapters consumed by sibling plugins
connector/codex_blender_connector/   the Connector Add-on
docs/                         architecture, technical solution, verification evidence
schemas/                      the seven JSON Schemas above
scripts/                      CLI entry points, launchers, validators
scripts/harness/              the transport-neutral Harness core
scripts/harness/commands/     the command registry
skills/                       26 Agent Skills
tests/                        37 test modules
vendor/jimeng_blender_uploader/   archived research material, not a runtime dependency
```

`docs/archive/legacy-uploader/` 保存已被取代的上传器时期架构与技术方案。它作为历史保留，运行时从不加载。

## 接口契约

| 接口 | 契约 |
|---|---|
| Codex 到 Harness | 本地传输上的闭合 JSON 请求 |
| Harness 到 Codex | 闭合 JSON 响应加产物回执 |
| Harness 到 Blender | 仅在主线程执行的已注册命令 |
| Blender 到同族插件 | 原子写入的 `ArtifactReceipt` `1.0.0`，以及 `bin/` 适配器 |
| Harness 到审计 | 每会话审计摘要与每产物的回执 |

模型导出会被重新导入隔离场景并检查预期结构。媒体输出用 ffprobe 独立探测。只有产物通过自身校验后才会写入回执。

## 配置优先级

从高到低：

1. 当前请求上的显式参数。
2. 会话携带并记入审计的 `ExecutionPolicy` 信封。
3. 会话的启动或 Connector 选项集。
4. 默认值 `interactive`。

省略策略时保持 `interactive`，因此既有调用方行为不变。更窄的策略永不被后续请求放宽：以 `review_only` 打开的会话即便请求携带授权声明，也会拒绝修改、导出与授权升级。

## 错误模型

| 情况 | 结果 |
|---|---|
| 未知命令 | 关闭式失败，不派发 |
| `expectedSceneRevision` 过期 | 在修改前拒绝 |
| 非幂等 `requestId` 重复 | 返回先前响应，不重复执行 |
| 路径在批准根目录之外 | 规范化解析后拒绝，含符号链接 |
| 事务中途异常 | 事务回滚，并报告恢复状态 |
| 校验失败 | 停下等待恢复；计划不继续推进 |
| 必需素材缺失且禁用代理 | 停下并请求用户提供素材 |
| 超出信封（覆盖、删除、专家 Python、未批准路径、远程预算） | 停下等待动作绑定授权 |

错误是结构化的，分支判断永不以本地化文案为依据。

## 幂等与恢复

里程碑批准绑定 `sceneRevision + snapshotId`，最终导出必须使用所绑定的修订号。长动画输出拆成两个可恢复作业：`RENDER_ANIMATION_FRAMES` 产出逐帧结果，`COMPOSE_VIDEO` 只消费完整且哈希校验通过的 `FrameSequenceReceipt`。显式恢复会复用已验证帧，只替换缺失或损坏的条目，因此被中断的渲染不会从第零帧重来。崩溃恢复会重开最后的持久检查点，只重放已提交的幂等命令。

## 实现阶段

| 阶段 | 内容 |
|---|---|
| Harness 内核 | 会话、防护、主线程队列、注册表、事务引擎 |
| 前台与策略 | 视口与播放命令、面板、`ExecutionPolicy` 传递、暂停与接管 |
| 能力覆盖 | 验收证据中记录的分期 P0–P9 领域构建 |
| 媒体流水线 | 帧序列渲染、独立 ffmpeg 合成、合成器与 VSE 交付 |
| 打包 | Connector 压缩包、Windows x64 Named Pipe 与恢复、发布门禁 |

## TDD 用例

测试套件按发布契约测试先行编写。代表性用例：

- 传输线程请求只有在 Blender 定时器泵动队列后才完成。
- 携带过期 `expectedSceneRevision` 的修改被拒绝，且不改变任何内容。
- 重复的非幂等 `requestId` 返回先前响应，且只执行一次。
- 注入失败后事务回滚，并报告恢复状态。
- 通过符号链接逃逸批准根目录的路径被拒绝。
- `review_only` 会话即便收到授权声明也拒绝修改。
- 接管或撤销之后排队的工作被拒绝，包括在此之前入队的工作。
- `COMPOSE_VIDEO` 拒绝不完整或哈希不匹配的 `FrameSequenceReceipt`。
- 帧与播放变更不递增内容修订号，也不写场景文件。

## 测试矩阵

| 维度 | 覆盖 |
|---|---|
| 测试模块 | `tests/` 下 37 个 |
| 运行模式 | 托管与 Connector 共用一套一致性套件 |
| 平台 | macOS Apple Silicon 已验证；Windows x64 为发布门禁要求 |
| 导出格式 | `.blend`、`.glb`、`.gltf`、`.fbx`、`.obj`、`.stl`、`.png`、`.jpg`、H.264 `.mp4` |
| 失败注入 | 事务回滚与崩溃恢复 |
| 技能 | 26 个 Skill 通过结构校验，并按行为评测进行路由 |

## 发布与回滚

发布要求一致性套件在两种运行模式下均通过、在 macOS Apple Silicon 与 Windows x64 上通过真实 Blender 运行时测试，且每种发布格式都有校验过的回执。当前证据中 Windows x64 托管模式与 Connector 运行时记为 `NOT RUN`，因为它们需要 Windows Blender 主机；它们仍是发布门禁，不是被豁免的要求。

回滚是一等运行时行为，而不是发布期事务：每个里程碑可逆，每次修改都做修订号校验，失败的事务恢复先前场景状态。分发产物是一个插件目录，因此降级即用先前版本替换该目录；不会对用户场景执行任何迁移步骤。
