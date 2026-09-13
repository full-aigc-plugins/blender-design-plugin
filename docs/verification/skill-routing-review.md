# Blender Skill 路由与命名审查

## 命名规范

参考 `codex-maya-use/inspect/diagnose/export-preview` 与 `codex-dreamina-3d-use/from-blender/resume`，本插件采用：

`codex-blender-<明确动作或单一领域>`

全部名称使用小写 ASCII、连字符、目录名与 frontmatter name 一致且少于 64 字符。移除两个职责过宽的旧名称：

- `codex-blender-sculpt-simulation`
- `codex-blender-tracking-sequence`

拆分为 `sculpt-surface`、`hair`、`simulation`、`tracking`、`sequence-editing`，并新增 `cinematography`、`quality-validation`、`background-jobs`。

## 路由优先级

1. 配方注册时声明的多 Skill 是最高优先级。
2. 跨领域命令使用命令级映射，例如 extended export、camera visibility、prop handoff。
3. 单一领域命令使用领域映射。
4. 只有没有专业映射的通用命令才回退到 design/use。

`job.submit` 另按 kind 声明条件 Skill：EXPORT/RENDER_STILL → render-compositing，BAKE_POINT_CACHES → simulation。

## 修复结果

- `scene.inspect` → inspect，而不是 scene-assembly。
- object transform/parent/visibility/duplicate/instance → scene-assembly；join/separate/apply/origin → hard-surface；create_curve → curves。
- animation → character-animation；camera → cinematography；validation → quality-validation，并为角色/镜头检查增加第二专业 Skill。
- job → background-jobs；asset pack/relative → render-compositing；extended export → export + render-compositing。
- runtime verification 不再统一指向 P1：每条 L3 命令关联所属阶段的真实 Blender 测试。
- `skillCoverage` 区分 domain-workflow、composite-workflow、lifecycle-inspection、lifecycle-routing、background-workflow 与 gated-expert-entry。

自动回归由 `tests/test_skill_routing.py` 验证具体命令映射、条件路由、阶段证据和角色分类。
