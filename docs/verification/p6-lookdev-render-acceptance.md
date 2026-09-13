# P6 外观、渲染、合成与扩展交付验收

结论：Blender 5.2.1 LTS / macOS Apple Silicon 达到 L3。

- 可复用 Shader node group 插入产品材质；64×64 Roughness 烘焙落盘并以 Non-Color 语义连接。
- 先保存工作副本，再路径相对化、pack 纹理；独立目录 `.blend` 重开后 packed image、材质组和 compositor 保留。
- Cycles 以 CPU、8 samples 实际配置；Eevee 请求按运行时枚举映射到 `BLENDER_EEVEE`。设备列表为空时未虚构 GPU。
- Z、Normal、Diffuse Color、Emission passes 已启用；独立 Beauty view layer 也通过 Z/Normal 配置；透明背景、曝光和输出尺寸均返回实际值。
- Blender 5.2 使用 `Scene.compositing_node_group` 与 Group Output；旧版兼容路径仍保留。Exposure→Color Balance→Glare→Output 连接通过检查。
- PNG、EXR、USDC、Alembic 与 packed `.blend` 均有大小和 SHA-256。USD 重导入 11 个对象、Alembic 10 个，EXR 为 320×320。
- EXR/USD/Alembic 使用独立 receiptVersion 2.0.0；旧 export.file 回执未改变。
- PNG 模型视觉检查确认产品材质、轮廓光和 Glare 可辨。

交付：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p6-render-20260913-v8`。

限制：本机未枚举到可用 Cycles GPU，所以仅证明 CPU 路径；Windows/GPU、复杂多层 EXR 和大型 USD 场景仍未达到 L4。
