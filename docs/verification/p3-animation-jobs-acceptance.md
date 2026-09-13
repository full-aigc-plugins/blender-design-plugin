# P3 高级动画、质量检查与后台任务验收

结论：Blender 5.2.1 LTS / macOS Apple Silicon 达到 L3；后台任务回执为独立 2.0.0 格式，旧同步导出回执保持不变。

## 动画与检查

- Blender 5.2 分层 Action 已实测，接口也兼容旧式 F-Curve 容器；完成曲线时间/数值缩放、插值与冗余点清理、NLA strip、Shape Key、同构骨架映射、相机路径、目标跟随和可控 Noise 手持响应。
- 独立质量命令输出对象/骨骼、帧区间、误差和 passed：支撑脚、肢长、道具释放/接回、穿地、相机可见性、位置/角度突变。
- 固定角色工程的交接、脚漂移、肢长、穿地和相机可见性通过；严格运动阈值正确报告超限帧，没有把预期告警吞掉。
- `advanced_animation.blend` 保存后由独立 Blender 重开，确认 layered actions、NLA、Shape Key、相机路径/朝向和 retarget Action 存在。
- 首/中/末三帧模型视觉检查确认相机路径变化时角色与长矛保持可读。

动画交付：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p3-animation-20260913-v4`。

## 后台任务

- 提交时 `save_as_mainfile(copy=True)` 生成任务快照；子 Blender 只写 `jobs/<jobId>`，输出有大小与 SHA-256。
- 子进程 GLB 只包含 `SnapshotOnly`，不包含提交后前台新增的 `AfterSnapshot`，证明旧任务绑定旧快照。
- 取消 4096×4096 渲染返回 cancelled；失联运行状态恢复为 interrupted/not-restarted，不自动重跑。
- 非后台 Blender 5.2.1 前台进程中，子任务运行时切换 FRONT、开始/停止播放、创建新对象和取消子任务均通过；父进程未被关闭。

后台最终证据：`/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p3-jobs-20260913-v2` 与 `/Users/wandl/workspaces/workspace-partme-ai/deliverables/codex-blender-p3-foreground-job-20260913`。

限制：当前后台 kind 为 EXPORT 与 RENDER_STILL；模拟烘焙将在 P5 接入。取消是进程级安全终止，不保证外部渲染器可保留部分帧。Windows 尚未验证，因此不是 L4。
