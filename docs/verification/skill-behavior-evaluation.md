# 制作 Skill 行为验收

这是一次真实任务前向验收，不是关键词扫描。固定模型配置为当前 Codex GPT-5；宿主为 macOS Apple Silicon、Blender 5.2.1 LTS；输入为用户批准的 P0–P7 计划与各阶段固定尺寸/帧范围。自动模式只操作授权输出目录，没有下载资产、安装扩展或触发外部付费。

| Skill | 固定任务 | 可观察行为与证据 | 结论 |
|---|---|---|---|
| scene-assembly | 稳定 ID、复制/实例、集合、导入 | 重命名后解析、共享/独立数据、OBJ/GLB/FBX/blend 追加链接 | PASS |
| hard-surface | 壳体、长矛、音箱 | 保留 helper 和 modifier 顺序；视觉失败后识别默认 Cube 遮挡并重验 | PASS |
| curves | Bezier 路径转 mesh | 控制点、handle、bevel、sampling、conversion | PASS |
| UV/material | 产品 UV 与 roughness | seam/unwrap/pack；Non-Color→Roughness；没有宣称 overlap 已检查 | PASS |
| character-rigging | 真 Armature 白模 | IK 控制器驱动、显式权重、骨长和脚锁；没有用分段物体关键帧冒充 | PASS |
| character-animation | 唯一长矛交接 | 释放距离/时长、接回连续性、重定时与视觉帧 | PASS |
| cinematography | 路径与手持镜头 | 相机跟随、目标可见性、Noise 手持和首中末帧 | PASS |
| quality-validation | 角色与镜头验收 | 脚漂移、肢长、接回、穿地、可见性与突变均返回具体帧/误差 | PASS |
| procedural-modeling | 废墟庭院 | 使用 socket identifier；发现旧 modifier 输入 API 失效后采用 5.2 interface value | PASS |
| sculpt-surface | 表面与笔刷 | 参数位移、remesh、Multires 和真实前台 brush | PASS |
| hair | 原生毛发 | CURVES、strand/point 数与 surface binding | PASS |
| simulation | 物理与缓存 | 刚体/布料/软体/Smoke bake/free | PASS |
| background-jobs | 快照隔离任务 | 前台继续操作、取消、失联不重跑；显式恢复只补缺失/损坏帧；序列 manifest 和快照哈希绑定 | PASS |
| render-compositing | packed lookdev 与长动画 | CPU 不冒充 GPU；持久 PNG/多层 EXR；File Output；独立 H.264 合成；v2/v3 receipts | PASS |
| grease-pencil | 两帧线稿 | 清理工厂默认层/材质，只保留请求内容，保存重开 | PASS |
| tracking | 20 帧 solve | CLIP_EDITOR solver 0.617493px、12 bundles | PASS |
| sequence-editing | VSE 输出 | Scene/Image Sequence/Text/Sound、Wipe/Speed、声音交叉淡化、Compositor Modifier、保存重开 | PASS |

失败处理也计入行为证据：壳体遮挡、庭院拱门越界、流体隐藏 bake、VSE 无音频、Blender 5.2 API 差异均先保留失败结果，再修正和重跑。Skill 结构另由 `skill-creator` validator 检查；结构通过不替代上述作品行为。

限制：这是一个固定模型和本机版本的真实前向样本，不证明所有未来模型版本都做出相同决策。Windows 与 Rigify generate 没有运行环境，因此不声称 L4。
