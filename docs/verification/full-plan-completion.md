# Codex Blender P0–P9 总验收

## 结论

P0–P9 的本地实现、macOS Apple Silicon 与 Windows Server 2025 x64 / Blender 5.2.1 LTS 真实后台工程验收已完成。发布版本为 0.3.0；GitHub、Windows artifact 与安装缓存继续作为独立门禁核验。

## 分阶段证据

| 阶段 | 实现与作品 | 最终证据 |
|---|---|---|
| P0 | 可查询目录、前台策略、平台矩阵 | `capability.list/describe`；foreground policy；163 tools |
| P1 | 稳定 ID、上下文、BMesh、7 类 modifier、curve、asset、壳体/长矛 | `codex-blender-p1-acceptance-20260913-v4` |
| P2-A | 五零件桌面音箱、18mm 壁厚、UV/材质、GLB 重导入 | `codex-blender-p2-product-20260913-v4` |
| P2-B | 16 骨骼、14 权重组、IK/极向、唯一长矛交接 | `codex-blender-p2-character-20260913-v3` |
| P3 | Layered Action、F-Curve 清理、NLA、Shape Key、retarget、相机路径/手持、质量检查、后台任务 | `codex-blender-p3-animation-20260913-v4`、`codex-blender-p3-jobs-20260913-v2` |
| P4 | Geometry Nodes 5.2 interface、参数庭院、稳定引用 | `codex-blender-p4-courtyard-20260913-v2` |
| P5 | 真 Sculpt brush、mask/remesh/Multires、Hair Curves、刚体/布料/软体/Smoke bake/free | `codex-blender-p5-simulation-20260913-v7`、`codex-blender-p5-sculpt-foreground-20260913` |
| P6 | Shader group、烘焙/pack、Cycles CPU/Eevee、view layers/passes、Blender 5 compositor、EXR/USD/Alembic | `codex-blender-p6-render-20260913-v8` |
| P7 | Grease Pencil、VSE H.264+AAC、20 帧 tracking solve、mask composite、Rigify optional adapter | `codex-blender-p7-gp-vse-20260913-v2`、`codex-blender-p7-tracking-20260913-v5`、`codex-blender-p7-compositor-20260913-v3` |
| P8 | 持久 PNG/多层 EXR、逐帧恢复、独立 FFmpeg、扩展 VSE、File Output 与 Compositor Modifier | `codex-blender-frame-pipeline-20260914-v6`、`codex-blender-vse-extended-20260914-v2`、`codex-blender-compositor-delivery-20260914-v4` |
| P9 | Rigify 受授权自动启用、真实生成、Windows x64 Named Pipe/恢复/打包 L4 | `codex-blender-rigify-install-20260914-v2`、GitHub run `34798159616` |

上述目录均位于 `/Users/wandl/workspaces/workspace-partme-ai/deliverables/`。最新 capability 快照位于 `codex-blender-full-plan-acceptance-20260914-v4`；Windows artifact 镜像位于 `codex-blender-windows-l4-34798159616`。

## 量化结果

- 工具：163 registered；136 L3；3 L4；24 L1。34/34 目录领域有注册命令。
- Skill：26 个分发 Skill；22 个被当前命令目录精确引用，4 个为 managed/connector/recover 等会话生命周期入口。真实固定任务行为见 `skill-behavior-evaluation.md`。
- 角色：肢长误差 0；释放距离≥5cm 连续 30 帧；接回位置跳变约 1.19e-7m、旋转 0°；骨盆移动时脚漂移 7.67mm；最低点高于地面。
- 产品：目标尺寸误差≤0.5%；壁厚参数、Boolean→Bevel→Subdivision、UV、packed texture 与 GLB reimport 通过。
- Tracking：12 tracks/12 bundles；平均重投影误差 0.617493px。
- VSE：320×240、24fps、2.083333s；H.264 video + AAC audio。
- P8：PNG 故障注入后保留第 1 帧、只补第 2/3 帧；多层 EXR 真渲染；独立 MP4 为 320×240、24fps、H.264。
- Python 回归：macOS 238 tests passed（1 个 Windows-only Named Pipe 测试跳过）；Windows 238 tests passed（1 个 POSIX mode-bit 测试跳过）；distribution、compileall、diff check、Connector package 通过。

## 明确保留的低成熟度

- Windows 前台 Blender UI/人工接管：GitHub Runner 无交互桌面，不标 L4；Linux 普通 CI 不替代 GUI。
- UV island overlap、专业角色重拓扑、成片级毛发/流体和复杂非同构 retarget 不在当前 L3 承诺内。
- `advanced.execute_python` 是 gated 专家入口，不计入领域覆盖。

## 发布门禁

0.3.0 已同步 validator、manifest、Connector Add-on、artifact producer、Dreamina handoff producer 和契约断言。公开 Marketplace source 指向 `https://github.com/partme-ai/codex-blender-plugin.git@main`。本地 `personal` 安装已移除，改由 GitHub `partme-ai-blender` Marketplace 安装；测试、能力目录、补帧视频和 Rigify 均从新缓存运行。最终缓存/源码/远端 SHA 在发布回执中核对。
