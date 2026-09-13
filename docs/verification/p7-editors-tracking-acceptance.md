# P7 其他 Blender 编辑领域验收

结论：Blender 5.2.1 LTS / macOS Apple Silicon 的 Grease Pencil、Tracking、VSE 和跟踪遮罩合成达到 L3；Rigify 仅完成可选适配与不可用状态验证。

## Grease Pencil 与 VSE

- Grease Pencil 只保留请求的 Action/Notes 图层和 Ink 材质；Action 在第 1、12 帧各有一条三点可编辑 stroke。
- Camera 预览能看到橙色笔画；`.blend` 重开后帧和 strokes 保留。
- VSE 含 Warm/Cool 图像条、21–31 帧 CROSS、Tone 声音条；音量 0.35，320×240、24fps、50 帧。
- MP4 为 H.264、2.083333 秒，ffprobe 另确认 AAC 音轨。抽取暖色与冷色帧完成视觉检查。

交付：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p7-gp-vse-20260913-v2`。

## 运动跟踪

- 前台非 background Blender 中生成 20 帧已知相机运动、12 个空间点；插入 12 条全帧 normalized markers。
- 在真实 CLIP_EDITOR 调用 Blender camera solver；12 个 track 均生成 bundle，平均重投影误差 0.617493px，小于 1px。
- tracking scene setup 成功并保存 `tracking_solution.blend`。

交付：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p7-tracking-20260913-v5`。

## 高级合成与扩展

- Blender 5.2 compositor node group 增加 Movie Clip、闭合四点 Mask、Alpha Over；16 节点/14 links 保存重开。
- Rigify status 实测 installed=false、enabled=false、operatorAvailable=false。生成命令已版本化适配，但本机未安装时返回 CAPABILITY_UNAVAILABLE，不尝试安装。因此 Rigify generation 保持 L1/不可用，不提升 L3。

合成交付：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p7-compositor-20260913-v3`。
