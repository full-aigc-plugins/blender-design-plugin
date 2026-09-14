# Blender 制作能力实施账本

规格事实源：本任务用户批准的《Codex Blender 插件完整能力覆盖与高级制作能力建设计划》。本文件记录实施和证据，不改变其验收要求；原 Harness 规格和前台执行策略继续生效。

## 边界与发布门禁

只修改 codex-blender-plugin；保留官方上传器和未提交前台改动。不增加计费、编剧或跨镜头制片能力。原生优先，不自动安装扩展或下载资产。继续 codex-blender/v1 与旧同步导出及回执。

L0=目录；L1=结构化接口；L2=配方与 Skill；L3=真实工程、视觉及交付；L4=恢复与版本/平台验证。三类覆盖（工具、Skill、真实工程）分别报告。注册、脚本可执行和 CI 通过均不是领域完成证明。

每个阶段按接口→配方→Skill→检查→真实作品推进；阶段验收未通过不推进后续制作阶段。

## 任务与依赖

- [x] P0：验收并固化已有前台、暂停接管、执行策略；审计全部命令、技能、测试与实际工程。
  - [x] 增加注册元数据及 capability.list/describe；保留旧列表契约。
  - [x] 目录列出没有实现的领域，不注册占位命令。
  - [x] 为每条现存命令补齐类型、前提、效果、当前可用性、Skill 和证据映射；未知项明确显示 unknown。
    - [x] 注册时补充预期字段类型、相关测试/路由 Skill、效果；后台视口及授权目录动态探测。
    - [x] 细化修改器/导出嵌套参数、目标对象/模式前提及正式制作证据。
    - [x] 修复基础创建的非法参数残留及修改器配置失败残留；拒绝父子关系循环。
  - [x] 完成版本、平台、前台运行验收矩阵及剩余缺口排序。
- [x] P1：统一上下文与稳定对象 ID；拓扑版本化选择；场景组织、对象编辑、BMesh 编辑、修改器生命周期、曲线与授权资产导入。公开命令制作参数化壳体和长矛。
- [x] P2-A：桌面音箱，独立零件、可编辑布尔/倒角/细分链、尺寸壁厚、UV/材质/布光、重开与 GLB 重导入。
- [x] P2-B：真正骨架蒙皮角色，IK/FK/权重/约束、支撑脚、唯一长矛握持释放飞行接回。高度及抛矛时点可修改；不得以逐帧分段球体替代。
- [x] P3：Action/F-Curve/NLA/重定向/形态键/相机；指定帧区间运动质量检查；快照隔离后台任务查询、取消与恢复，前台可接管。
- [x] P4：Geometry Nodes 版本化 socket 接口、图检查与资产实例，参数化废墟庭院重建与稳定引用。
- [x] P5：雕刻/遮罩/Multires/重网格/人工接管、毛发、刚体/布料/软体/流体；缓存失效、重算、取消恢复。重网格不称专业重拓扑。
- [x] P6：完整材质/纹理/烘焙/依赖打包、设备探测与 CPU 降级、passes/色彩/合成；探测 EXR/USD/Alembic，独立目录重开验证。
- [x] P7：Grease Pencil、已知素材运动跟踪误差、VSE 时间线与输出、高级合成、已安装 Rigify 可选适配。
- [x] P8：持久 PNG/多层 EXR 序列契约、逐帧哈希、显式断点补渲、独立 FFmpeg 合成；Scene/Image Sequence/Text/Speed/完整转场语义及 VSE Compositor Modifier。
- [x] P9：Rigify 受授权自动启用/官方安装降级与 Windows x64 L4。
  - [x] macOS Blender 5.2.1 检测并启用捆绑 Rigify、保存偏好、生成 Human Meta-Rig 控制骨架；无下载。
  - [x] Windows 5.2.1 x64 官方 ZIP/SHA-256、后台恢复、FFmpeg、Rigify、Named Pipe 与 Connector workflow 成功。
- [ ] 发布门禁：
  - [x] 版本提升到 0.3.0，并同步 manifest、Connector、producer 与回执契约。
  - [x] 提交全部当前改动、推送 `main` 并核对本地/tracking/远端 SHA。
  - [x] 从 GitHub Marketplace 重装 0.3.0 缓存，并从缓存运行测试、能力目录、补帧视频和 Rigify 复验。

## 统一验收

命令测试→真实 Blender→完整作品→固定输入的 Skill 行为。保存、重开、编辑、渲染、重导入均需实际执行。任何阶段不以 tasks 勾选为证据。

米制测试：肢长误差≤0.5%；握持≤5mm；脱手≥5cm 且≥6帧；接回跳变≤1cm/2°；支撑脚漂移≤1cm；指定代理穿地≤2mm；产品尺寸误差≤0.5%；无 NaN/Inf/丢失依赖，指定封闭实体没有意外开放边与退化面。另做轮廓、节奏、接触及构图视觉验收。

macOS Apple Silicon 本机基线需记录实测版本；Windows x64 仍待发布验证；Linux CI 不作为 GUI 兼容证明。每阶段交付能力目录、接口、Skill、配方、blend、预览、检查报告、恢复与兼容矩阵。达到 L3 再考虑阶段发布，未测试能力保持实验状态。

## 当前证据

P0–P7 的 L3 证据分别记录在 `docs/verification/`；能力目录逐命令区分 L1/L2/L3，Rigify generate 等未验证能力保持不可用或较低成熟度。最终回归数字以完成报告中的新鲜验证为准。
当前新鲜证据为 macOS/Windows 239-test 基线、26 个 Skill 结构/路由校验、163 条工具的真实能力目录、P8/P9 Blender 5.2.1 验收、分发校验、Connector package、Windows L4 和 GitHub Marketplace 缓存复验；总报告见 `docs/verification/full-plan-completion.md`。
