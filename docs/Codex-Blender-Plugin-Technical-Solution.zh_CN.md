# Blender Design 插件技术方案

> **文档信息**
>
> | 字段 | 值 |
> |---|---|
> | 状态 | `blender-design` `0.3.0` 已实现；Windows 运行门禁记为 `NOT RUN` |
> | 范围 | 技术选型、契约、配置优先级、错误模型、测试与发布规则 |
> | 读者 | 扩展或评审本插件的实现者 |
> | 运行证据 | [harness-runtime.md](verification/harness-runtime.md) |

## 1. 技术决策

在用户自己的 Blender 内运行受约束的本地 Harness，由一套封闭且版本化的 JSON 命令协议驱动。

### 技术选型

| 选择 | 理由 |
|---|---|
| 只用 Blender Python API，不引入 C++ 或外部 DCC SDK | 插件必须能跑在用户自己的 Blender 5.2.1 LTS 里，不需要构建步骤 |
| macOS 用 Unix Domain Socket，Windows 用 Named Pipe，并保留令牌化环回 TCP 回退 | 本地传输既不暴露端口，又能覆盖两个发布门禁平台 |
| 版本化协议上的闭合 JSON 命令文档 | Codex 可以在派发前校验请求，未知命令关闭式失败 |
| 单一命令注册表，由两种运行模式共用 | 托管模式与 Connector 模式无法漂移成两套能力集 |
| Python 3 `unittest` | 无第三方测试依赖，测试能在运行插件的同一环境里跑 |
| `vendor/` 下供应商视口渲染器 | 把官方上传器的渲染行为作为隔离研究材料保留，而不是重新实现 |
| 通过 ffprobe 独立探测媒体 | 文件存在不等于文件正确 |

### 备选方案

| 备选方案 | 被否的原因 |
|---|---|
| 暴露一个通用 Python 执行命令 | 会让任意执行从模型编写的参数抵达 |
| 通过网络端口暴露 Harness | 无收益地把攻击面扩展到本机之外 |
| 自动安装 Connector Add-on | 未经同意就写入用户的 Blender |
| 把命令退出码当作交付证据 | 退出码无法证明产物正确 |
| 让两种运行模式各自演进注册表 | 必然导致模式之间出现静默的能力差异 |

## 2. Blender 探测与启动

托管模式解析 Blender 可执行文件，然后用临时引导脚本启动它（`managed_launcher.py` 调用 `managed_bootstrap.py`），不写入任何偏好设置或插件。Connector 模式完全不启动：`connector/codex_blender_connector/` 中的插件在已经运行的 Blender 内注册，并宣告同一套协议。

两种模式随后收敛到同一套发现握手：打开传输、交换会话密钥、协商 `codex-blender/v1`，并从命令注册表发布能力清单。`launch_harness.py` 与 `harness_cli.py` 是 Codex 使用的入口。

## 3. 命令与 Schema 契约

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

## 4. 目录结构

```text
.codex-plugin/plugin.json     plugin manifest (id blender-design)
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

`docs/archive/legacy-uploader/` 保存着已被取代的上传器时代架构与技术方案。它作为历史保留，运行时永不加载。

## 5. 接口契约

| 接口 | 契约 |
|---|---|
| Codex 到 Harness | 本地传输上的闭合 JSON 请求 |
| Harness 到 Codex | 闭合 JSON 响应加产物回执 |
| Harness 到 Blender | 只在主线程执行的已注册命令 |
| Blender 到兄弟插件 | 原子写入的 `ArtifactReceipt` `1.0.0`，外加 `bin/` 适配器 |
| Harness 到审计 | 每会话审计摘要与每次导出回执 |

模型导出会被重导入到隔离场景并检查预期结构。媒体输出用 ffprobe 独立探测。只有产物通过自身校验之后才会写回执。

## 6. 配置优先级

优先级从高到低：

1. 当前请求上的显式参数。
2. 会话携带并记入审计的 `ExecutionPolicy` 封装。
3. 会话的启动或 Connector 选项集。
4. 默认值 `interactive`。

省略策略时保持 `interactive`，使既有调用方行为不变。更窄的策略绝不能被后续请求放宽：以 `review_only` 打开的会话会拒绝修改、导出与授权升级，即使请求携带授权声明。

## 7. 错误模型

| 情形 | 结果 |
|---|---|
| 未知命令 | 关闭式失败，不派发 |
| `expectedSceneRevision` 过期 | 在修改之前拒绝 |
| 非幂等 `requestId` 重复 | 返回先前响应，不重复执行 |
| 路径在已批准根目录之外 | 规范化解析之后拒绝，含符号链接 |
| 事务中途异常 | 事务回滚；并报告还原状态 |
| 校验失败 | 停下进入恢复；计划不再继续 |
| 必需素材缺失且禁止替代 | 停下并索要用户素材 |
| 超出封装边界（覆盖、删除、专家 Python、未批准路径、远端预算） | 停下等待动作绑定授权 |

错误是结构化的，本地化消息永远不作为分支条件。

## 8. 幂等与恢复

里程碑批准绑定 `sceneRevision + snapshotId`，最终导出必须使用该绑定修订号。长动画输出被拆成两个持久任务：`RENDER_ANIMATION_FRAMES` 产出逐帧输出，`COMPOSE_VIDEO` 只消费一份完整且哈希校验通过的 `FrameSequenceReceipt`。显式续跑会复用已验证帧，只替换缺失或损坏的条目，因此中断的渲染不会从第零帧重来。崩溃恢复会重开最后一个持久检查点，只重放已提交的幂等命令。

## 9. 实施阶段

| 阶段 | 内容 |
|---|---|
| Harness 核心 | 会话、守卫、主线程队列、注册表、事务引擎 |
| 前台与策略 | 视口与播放命令、面板、`ExecutionPolicy` 传播、暂停与接管 |
| 能力覆盖 | 记录在验收证据中的分阶段 P0–P9 领域建设 |
| 媒体管线 | 帧序列渲染、独立的 ffmpeg 合成、合成器与 VSE 交付 |
| 打包 | Connector zip 打包、Windows x64 Named Pipe 与恢复、发布门禁 |

## 10. 测试策略

测试套件是按已发布契约先写测试的。代表性用例：

- 传输线程请求只有在 Blender 定时器泵动队列后才会完成。
- 携带过期 `expectedSceneRevision` 的修改被拒绝，且不产生任何变更。
- 重复的非幂等 `requestId` 返回先前响应，且只执行一次。
- 注入的失败会让事务回滚，并报告还原状态。
- 通过符号链接逃出已批准根目录的路径会被拒绝。
- `review_only` 会话即使收到授权声明也拒绝修改。
- 接管或吊销之后，队列工作会被拒绝，包括此前已入队的工作。
- `COMPOSE_VIDEO` 会拒绝不完整或哈希不匹配的 `FrameSequenceReceipt`。
- 帧与播放类变更不会递增内容修订号，也不写场景文件。

| 维度 | 覆盖 |
|---|---|
| 测试模块 | `tests/` 下 37 个 |
| 运行模式 | 托管与 Connector 共用同一套一致性测试 |
| 平台 | macOS Apple Silicon 已验证；Windows x64 由发布门禁要求 |
| 导出格式 | `.blend`、`.glb`、`.gltf`、`.fbx`、`.obj`、`.stl`、`.png`、`.jpg`、H.264 `.mp4` |
| 故障注入 | 事务回滚与崩溃恢复 |
| Skills | 26 个 Skill 通过结构校验，并按行为评估路由 |

## 11. 发布与回滚

发布要求一致性测试在两种运行模式下都通过、在 macOS Apple Silicon 与 Windows x64 上有真实 Blender 运行测试，并且每种发布格式都有已验证回执。Windows x64 非侵入模式与 Connector 运行期在当前证据中记为 `NOT RUN`，因为它们需要 Windows Blender 主机；它们仍是发布门禁，而不是被豁免的要求。

回滚是一等的运行时行为，而不是发布期才考虑的事：每个里程碑可逆，每次修改都做修订校验，失败的事务会还原先前的场景状态。分发产物是一个插件目录，因此降级就是把目录替换为先前版本；不会对用户场景执行任何迁移步骤。

## 12. 证据映射

| 断言 | 证据 |
|---|---|
| Harness 核心与命令注册表 | `scripts/harness/`、`schemas/` |
| 托管与 Connector 一致性 | `tests/` 与 [harness-runtime.md](verification/harness-runtime.md) |
| 导出校验 | [harness-runtime.md](verification/harness-runtime.md)，独立重导入与探测 |
| 能力清单 | [capability-counts.json](verification/capability-counts.json) |
| 上传器时代归档 | `docs/archive/legacy-uploader/` |
