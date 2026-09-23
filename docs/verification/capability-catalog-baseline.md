# 能力目录首批实现验收

状态：P0 部分完成；本记录不是 P0–P7 完成报告。既有前台改动保留，未重新发布或重装缓存。

## 已执行

- `python3 -m unittest discover -s tests -q`：182 项通过，含目录查询、分页、过滤、旧返回格式、无占位注册、暂停/只读期间查询不增加 revision。
- `Blender --background --factory-startup --python-exit-code 1 --python tests/runtime/capability_catalog_smoke.py`：退出码 0。
- 真实运行版本：Blender 5.2.1 LTS，hash `9e2066aef7ef`。此次为后台隔离测试，不代表 GUI 或其他平台通过。
- 无授权导出根目录的 registry：36 条命令；有导出根目录时还会注册 export.file，不能把固定数量当永久接口契约。
- 非法向量长度、NaN、Infinity 在创建前失败，不残留对象；修改参数较晚的字段非法时，较早的 location 不会先被修改。

## 目录 API

使用既有 codex-blender/v1 请求封装。下面仅为 arguments：

| 命令 | 参数 | 返回 |
| --- | --- | --- |
| capability.list | `{ "domain": "mesh", "limit": 50, "offset": 0 }` | items、total、nextOffset、全领域 domains |
| capability.describe | `{ "id": "object.transform" }` | 输入字段、风险、成熟度、上下文、证据、可用性 |

domain/maturity 可省略；maturity 使用 L0–L4；offset 为非负整数，limit 为 1–100。L0 表示领域没有注册命令，过滤 L0 不会产生虚构接口。领域有部分命令时显示 partial，不等于领域全部支持。旧 session.capabilities 保持原 command/risk 列表。

## 仍需完成

- 现存命令的详细参数类型、上下文、版本、Skill、可用性探测与证据映射尚未全部补齐。未知字段明确返回 null/unknown/空证据，不作为保证。
- 现有目录尚无已批准的 L3/L4 制作能力记录；目录回归通过不能提升制作成熟度。
- 尚需固化前台基础验收和完整覆盖矩阵，之后按实施账本进入 P1。P1–P7 制作配方、领域工具及作品本轮尚未完成。
- 入口 Skill 的改动是能力选择约束；格式校验不等于固定模型配置下的行为验收。

## 后续增量：运行条件与证据关联

本次完整回归更新为 **188 项通过**，目录专项 14 项。真实 Blender 5.2.1 LTS 隔离脚本再次通过，输出目录快照与检查回执：

- `/tmp/blender-capability-audit.LozsCe/catalog.json`
- `/tmp/blender-capability-audit.LozsCe/verification.json`

以上为本地临时测试证据，不是插件分发资产；重跑脚本并在 `--` 后传入新目录可以重建。

每次注册现有命令时，目录现在关联输入字段的预期类型、代码位置、相关测试、路由 Skill、场景修改和耗时属性。既有处理器存在的类型转换行为未被悄悄改成严格 schema 校验；modifier.settings、导出 parameters 等嵌套结构仍需逐项细化。Skill 关联明确标为 routing-only。

动态探测覆盖：后台没有视口、没有 VIEW_3D 窗口、未授权输出根目录、未授权资产根目录。查询不会授权任何动作，也不验证尚未提供的对象或路径。官方上传器继续通过其 inspect 查询状态，目录不猜测可用性。

修复目录可信度边界：元数据不能覆盖命令 ID、风险或输入契约；探测失败返回 unknown 且不泄露异常细节；L3 同时要求 Skill、运行、视觉和交付证据，L4 另需恢复兼容证据。证据引用本身仍需人工/真实工程验收，非自动认证。

### 平台与阶段门禁

| 项目 | 当前证据 | 结论 |
| --- | --- | --- |
| macOS Apple Silicon / Blender 5.2.1 LTS 后台 | 本次隔离查询及前置校验 | 目录测试通过，非作品验收 |
| 同版本 Managed / Connector 前台 | foreground-policy-runtime.md 既有记录 | 保留证据；此次未重跑整套 GUI |
| 多 Blender 实例窗口焦点 | 既有记录指出错误实例选择 | 未解决，不承诺 OS 前台激活 |
| Windows x64 | 无运行证据 | 未验证 |
| Linux 图形界面 | 无运行证据 | 未验证，普通 CI 不替代 |

剩余顺序：完成复杂参数与当前模式/对象前提审计 → 复核正确实例前台可见与接管 → 固化 P0 → P1 上下文/拓扑/模型操作 → P2 产品和绑定角色双作品。P0 尚未整体完成；P1–P7 仍未进入验收。

## 创建失败一致性修复

后续完整回归 **195 项通过**，真实 Blender 5.2.1 LTS 隔离脚本退出码 0。

- 相机焦距、灯光能量/颜色/尺寸、材质 PBR 参数、曲线倒角、文字尺寸/挤出深度在创建前验证。
- 对上述数值拒绝布尔值、NaN/Infinity 和非法范围。此前部分属性通过 float 接受数字字符串，现在需使用 JSON number；这是明确的输入约束收紧，不改变合法数值请求。
- 父子关系拒绝自循环及祖先循环，失败不修改原层级。
- 修改器 settings 必须为对象；配置失败仅移除本次新建的修改器，不触碰原修改器链。此为失败清理，不替代 P1 的 RNA 前置验证及统一事务。
- 真实 Blender 检查覆盖创建无残留、变换无部分修改、修改器配置失败无残留。父子循环另有单元回归，尚不代替完整骨架制作测试。

仍未宣布 P0 或全计划完成；正式领域工具、配方与作品验收按实施账本继续。

## 生命周期命令毕业至 L3

13 条核心生命周期/内省命令通过真实 Blender 5.2.1 LTS 后台运行证据从 L1 提升至 L3：

- `capability.list`, `capability.describe`
- `session.status`, `session.capabilities`, `session.pause`, `session.resume`, `session.set_progress`
- `scene.inspect`
- `object.create_curve`, `object.create_text`
- `material.attach_image_texture`
- `playback.set_frame`
- `production.status`

验收脚本 `tests/runtime/lifecycle_commands_acceptance.py` 在真实 Blender 后台运行，逐条命令执行并保存证据到 `lifecycle_acceptance.json`。

**前台阻塞（5 条）**：`view.set`, `view.focus`, `view.present`, `playback.set`, `preview.capture` 需要前台 VIEW_3D 区域，在后台模式下不可用，保持 L1。其毕业依赖 Task 17（macOS/Windows 前台认证）。

**专家级排除（1 条）**：`advanced.execute_python` 标记为 `expert` 类，不计入生产覆盖。

**证据范围**：本次验收在 Blender 5.2.1 LTS / darwin / arm64 / managed 模式下运行。生产配置文件的验证器**不检查 RuntimeIdentity**——证据适用于所有身份，不存在按身份隔离的机制。验收脚本的输出（`lifecycle_acceptance.json`）记录了实际运行的版本、平台和架构，读者可据此判断覆盖范围。其他版本和平台的证据由 Task 4 的覆盖矩阵建立。

**生产状态**：`production.status` 返回 `l1Commands` 字段，列出仍在 L1 的生产范围内命令。修复证据路径锚点验证（C1）后，`blockedCommands` 为空，`status` 为 `ready`。`l1Commands` 包含 5 条前台阻塞命令（stub 模式）或 6 条（含 `export.file`，需 approved output root）。
