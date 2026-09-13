# P5 表面、毛发与模拟验收

结论：Blender 5.2.1 LTS / macOS Apple Silicon 达到 L3。

- 拓扑选择驱动 mask 与位移；Voxel Remesh 会提升 topologyVersion；Multires 两级和 Decimate/Shrinkwrap cleanup 保持可编辑。另在真实前台 VIEW_3D 执行 Sculpt brush stroke，最大顶点位移约 0.17747m。cleanup 明确不称生产级角色重拓扑。
- 原生 CURVES 对象含 3 条 Hair Curves、9 个点并绑定指定表面；不是普通 Curve 冒充。
- 刚体从 2.5m 落至 0.25m；布料从 2.5m 下落并在球形碰撞体上最低约 0.677m；视觉预览可辨。
- Cloth、Soft Body、Rigid Body、Collision、Smoke Domain 均有结构化配置。Smoke 为 5 帧、resolution 16 的短测试。
- `BAKE_POINT_CACHES` 子进程同时烘焙 point cache 与 Fluid；所有子缓存重定向至任务目录。872KB 级 `.blend` 重开后 Cloth 与 Fluid 均报告 baked，可显式释放并变为未烘焙。
- 隐藏的流体对象仅在 bake/free 期间临时显示，完成后恢复，不修改前台可见性约定。

交付：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p5-simulation-20260913-v7`。最终子缓存目录使用安全索引/名称并限制在任务目录。
前台笔刷证据：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p5-sculpt-foreground-20260913`。

限制：三条毛发和低分辨率 Smoke 是接口验收夹具，不代表发型或影视流体质量；模拟只要求物理/视觉容差，不要求跨设备字节一致。
