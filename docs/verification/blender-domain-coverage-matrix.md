# Blender 全领域覆盖矩阵

> 本矩阵的域/命令数量以 [`capability-counts.json`](capability-counts.json)（由注册表生成）为准，不在此手工维护计数。

代码事实源：运行时命令注册表与 `capability.list/describe`。本表是 P0 审计快照；注册命令、Skill 和真实验收分别计算。

| 领域 | 工具覆盖 | Skill 覆盖 | 真实验证 | 当前成熟度/缺口 |
| --- | --- | --- | --- | --- |
| 场景/对象/集合 | 单位、稳定 ID、局部/世界变换、父子保持世界坐标、复制/实例、合并/分离、可见性、原点、应用变换 | hard-surface + router | Blender 5.2.1 后台真实测试及 P1 工程重开 | L3（macOS 基线）；其他平台未验证 |
| Mesh | indices/spatial/connected/normal 选择；挤出、内插、倒角、细分、桥接、焊接、删除、三角化、法线重算；拓扑版本 | hard-surface | 九类操作真实测试；开放曲面语义验证 | L3（P1 范围）；更高级拓扑 L0 |
| Modifier | Mirror/Array/Bevel/Subdivision/Solidify/Boolean/Decimate 生命周期 | hard-surface | 七类在真实 Blender 创建、配置、排序、启停、应用、移除 | L3（首批七类） |
| Curve | POLY/Bezier、控制点、手柄、圆形截面、采样、转 Mesh | curves | 真实工程验证 | L3（单 spline/圆截面）；自定义 profile L0 |
| Asset/文件导入 | OBJ/GLB/GLTF/FBX；blend append/link | router | 本机生成固定资产并真实重导入 | L3（本机）；外部复杂资产兼容未覆盖 |
| 材质/相机/灯光 | PBR、语义贴图、节点组、烘焙、相机指向、灯光 | UV/material + render | 音箱重开、烘焙、packed lookdev | L3（测试范围）；复杂 shader library 仍部分 |
| 动画 | 帧/pose/constraint keyframe、Blender 5 layered Action、F-Curve、NLA、Shape Key、同构 retarget、相机路径 | character animation | P2/P3 工程与首中末帧 | L3（基础重定向）；高级非同构映射仍部分 |
| Rig/Constraint | Armature、显式权重、IK/pole/FK、limit、Child Of prop | character rigging | 真骨架持矛角色、重开与量化检查 | L3 |
| UV | seam、unwrap、pack、缺失/越界/退化检查 | UV/material | 产品工程与 GLB 重导入 | L3；重叠检测未支持 |
| Geometry Nodes | interface、node、link、参数、modifier input 的 5.2/旧版映射 | procedural modeling | 参数化庭院重建、重开和视觉 | L3（支持节点白名单） |
| Sculpt/Retopo | mask、法线/方向位移、Voxel Remesh、Multires、Decimate/Shrinkwrap | sculpt/simulation | 表面夹具与预览 | L3（接口范围）；不称专业重拓扑 |
| Hair | 原生 Hair Curves strand/point/surface | sculpt/simulation | 3 strand/9 point 工程 | L3（基础） |
| Simulation | 刚体、碰撞、布料、软体、Smoke、缓存查询/释放 | sculpt/simulation | point cache + Fluid 子进程烘焙 | L3（低分辨率夹具） |
| Render/Compositor | Eevee/Cycles、设备/CPU、passes、颜色、节点组、跟踪 mask | render/compositing | packed product、EXR 和 tracking composite | L3（本机 CPU） |
| Background jobs | snapshot submit/status/cancel/recover，Export/Still/Point+Fluid bake | render + sculpt | 前台并行、隔离、取消、恢复 | L3；Windows 未验证 |
| Grease Pencil | 层、材质、stroke、frame | Grease Pencil | 可编辑 2D/3D `.blend` 与视觉 | L3（基础） |
| Tracking | clip、markers、foreground solve、scene setup、error | tracking/sequence | 20 帧/12 bundle，0.617493px | L3 |
| Sequence Editor | image/movie/sound、trim/move/CROSS/volume/output | tracking/sequence | H.264+A​AC MP4、重开 | L3（基础） |
| Optional extensions/Rigify | status + generate adapter | character rigging | 本机 unavailable 状态验证 | status L3；generate L1/unavailable，不自动安装 |
| Expert Python | 显式 gated 入口 | router | AST 限制测试 | L1 专家入口；不计入任何语义领域覆盖 |
| Official uploader | 兼容适配保留 | jimeng-web | 既有适配测试 | 独立兼容能力，不属于本计划制作覆盖率 |

## 平台与运行模式

| 环境 | 证据 | 结论 |
| --- | --- | --- |
| Blender 5.2.1 LTS / macOS Apple Silicon / 后台 | P1 foundation、mesh、modifier、curve/asset、recipe、保存重开 | P0/P1 当前基线 |
| 同版本 Managed/Connector 前台 | 原生面板、视图、播放、暂停/恢复与策略验收记录 | 基础通过；多实例 OS 焦点不承诺 |
| Windows x64 | 无当前实机证据 | 未验证，不得标 L4 |
| Linux CI | Python/分发回归 | 不等于 Blender GUI 或 GPU 验证 |

P0 的完成含义是目录、缺口优先级、版本/平台和前台基础已审计并如实记录，不代表 Blender 全领域实现。后续仍按 P2→P7 消除 L0/部分覆盖。
