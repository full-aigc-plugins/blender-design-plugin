# P4 程序化庭院验收

结论：Blender 5.2.1 LTS / macOS Apple Silicon 达到 L3。

- Geometry Nodes 使用 group interface socket identifier；针对 Blender 5.2 `modifier.properties.inputs.<identifier>.value` 与旧 ID-property 方式做版本适配。
- 节点图含 Group Input/Output、面分布、Icosphere、实例、Realize、Join，共 7 节点、8 条连接；修改器输入可通过名称解析到稳定 identifier。
- 庭院 Ground、Arches、Steps、Slabs 名称及 object ID 在尺寸 10×7→12×8m、拱门 3→5、碎石密度 1.5→3 后保持不变。
- 保存重开后节点接口和 Array count=5 保留。模型视觉检查确认 5 个竖直拱门位于庭院范围内，碎石、台阶和石板可读。

交付：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p4-courtyard-20260913-v2`。

限制：当前配方是程序化白模环境，不是破损雕刻或完整建筑生成器；更复杂属性域与自定义 node asset library 尚未覆盖。
