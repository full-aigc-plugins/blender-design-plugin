# P2-A 桌面音箱验收

结论：Blender 5.2.1 LTS / macOS Apple Silicon 达到 L3。该结论只覆盖 P2-A，不覆盖角色绑定或其他平台。

- 版本化 `recipe.desktop_speaker` 通过公开命令创建 Housing、Grille、Knob、Interface、Base 五个独立零件。
- 机壳目标尺寸 0.42×0.26×0.68m，逐轴误差不超过 0.5%；壁厚 0.018m 可调，内部 cavity helper 保持线框可编辑，修改器为 Boolean→Bevel→Subdivision。
- Housing 与 Grille 已标 seam、展开、打包并通过当前 UV 缺失/越界/退化检查。当前检查器尚不检测岛重叠，限制保留。
- 粗糙度测试贴图通过批准目录加载，使用 Non-Color 并连接 Principled Roughness；节点查询确认连接。
- `.blend` 保存重开后零件、材质、UV 与修改器完整；GLB 重导入得到 7 个对象和 7 个材质，符合该测试工程范围。
- 相机近景、正视、侧视、顶视均已生成并进行模型视觉检查；机壳、网罩、旋钮、接口、底座和倒角轮廓可辨。

交付目录：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p2-product-20260913-v4`。GLB 使用 renderable 过滤，仅保留五个产品零件和测试地面，不导出 cavity helper。

未覆盖：复杂外部 FBX 材质差异、UV 重叠、纹理打包/烘焙、Cycles 设备与 Windows。它们属于后续阶段。
