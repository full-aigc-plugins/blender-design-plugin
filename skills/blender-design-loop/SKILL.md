---
name: blender-design-loop
description: Build a Blender scene that matches a target image via a closed dream → build → screenshot → critique → iterate loop. Use when the user says "dream loop", "iterate until it matches", "match this screenshot", "visual quality loop", or asks to refine a Blender scene against an in-engine target render. Combines scene.screenshot for capture, blender-harness JSON commands for build, and a fresh-context vision-rubric judge subagent for critique. Sourced from achimala/dream-loop (MIT, © 2026 Anshu Chimala) — pattern only, no code copied.
license: Apache-2.0
---

# blender-design-loop

This skill is the **orchestrator** for a closed-loop visual-quality
workflow against a Blender scene. The pattern is taken from
[achimala/dream-loop](https://github.com/achimala/dream-loop) (MIT,
© 2026 Anshu Chimala) — the loop itself, the rubric, and the
discipline rules. **No code is copied from dream-loop**; only the
orchestration pattern, which is implemented by referring to sibling
skills already shipped with this plugin.

## When to use

Use this skill when the user wants a Blender scene that matches a
visual target and is willing to wait while a loop refines it:

- "Build a Blender scene that matches this reference image."
- "Dream-loop this: iterate on the scene until it looks right."
- "Use vision critique to refine my current scene."
- "Close the gap between my live screenshot and the target."

Do **not** use this skill when:

- The user wants a one-shot render and is happy with it as-is (use
  `blender-design` or `blender-harness` directly).
- The target is not a single in-engine screenshot (e.g. "make it
  look like a photo of the Eiffel Tower" — too abstract; first
  produce the target render, then run this skill).
- The user is on a low-quota subscription and only wants the cheapest
  possible path — see Plus vs Pro below; if even Plus mode is too
  expensive, do a manual brief-driven build instead.

## Plus vs Pro tier routing

dream-loop's original discipline splits by subscription tier because
a strong orchestrator model (Pro) can also be the judge, while a
weak orchestrator (Plus) must delegate every implementation to a
worker subagent and ask the user to commit every 3 rounds. Mirror
the same here:

| Mode | Tier | Orchestrator | Build | Critique | Exit |
|---|---|---|---|---|---|
| **Plus** | Low-quota (e.g. ChatGPT Plus) | Smallest available model | Worker subagent, fresh context per round, 3 rounds max then ask | None — orchestrator inspects and decides | 3 rounds then mandatory user checkpoint |
| **Pro** | High-quota (e.g. ChatGPT Pro) | The current executing model | Orchestrator may build directly, OR spawn worker subagents | Fresh-context judge subagent, 4-dim rubric → total /10 | score ≥ 8 / stall / ask user |

The user rarely tells you the tier explicitly; if you don't know,
ask one focused question. Default to **Plus** when the user has not
specified — it is safer and cheaper.

## The 5-stage loop

Every iteration runs these five steps in order. Detailed rules are
in [references/workflow.md](references/workflow.md); the rubric
language is in [references/rubric.md](references/rubric.md).

```text
Dream (target.png) ─┐
                    │
                    ▼
                  Build ──→ Screenshot ──→ Critique ──→ Exit? ──→ (no) ──→
                                                                              │
                                  (yes) Done ◄────────────────────────────────┘
```

### Step 1 — Dream

Produce (or accept) a target PNG. The target is the ground truth the
live scene must converge toward. If the user supplies one, use it
directly. Otherwise generate one via a sibling image-gen skill:

- `image-factory-use` → `image-factory-run` (Codex CLI backend)
- `baoyu-image-gen` (multi-provider)
- `dreamina-design-use` → `dreamina-cli-text2image` (Dreamina backend)

Store the target at `.blender-loop/target.png` and **do not regenerate
it mid-loop** — convergence needs a fixed reference.

If the user has an existing Blender project and wants iteration on
top of it (rather than a fresh scene), capture the current state
once, pass it as a baseline image, and ask the image-gen skill to
produce an *improved* target rather than a divergent one.

### Step 2 — Build

For Plus mode: spawn a worker subagent with **fresh context** (no
fork, no shared thread history) per round. Give it:

- The absolute path to the target PNG
- The latest live screenshot (if round > 1)
- The previous round's judge verdict (if round > 1)
- A pointer to this skill's references/workflow.md for the full
  directive language
- One sentence: "close the gap between the live scene and the target.
  Do not assume what I want — read the brief and the screenshots."

The worker uses `blender-harness` to mutate the scene: JSON commands
over `harness_cli.py`, transactions with `expectedSceneRevision`,
L3+ capability maturity only. The orchestrator **must not** itself
build in Plus mode — that defeats the cost model.

For Pro mode: orchestrator may either build directly or delegate to
a worker subagent as in Plus. Direct build is preferred when the
worker would just replay the orchestrator's reasoning — subagents
are most useful when their fresh context avoids the orchestrator's
own bias.

### Step 3 — Screenshot

After every build step, capture a PNG of the current scene state
using the new `scene.screenshot` command:

```text
scene.screenshot
  path: ".blender-loop/round-N.png"
  width: 1024  height: 1024
  format: png
  overwrite: true
```

The receipt's `sha256` is your stable identifier for the round;
record it alongside the round number. See `blender-harness` for the
full command surface.

### Step 4 — Critique

For Plus mode: orchestrator opens both PNGs side-by-side, writes
a concrete gap list, and decides what the worker should change in
the next round. **Never describe feedback vaguely** ("make it look
better"). Always name the specific gap ("key light comes from the
wrong side", "shadow under the arch is too dark", "materials read
as plastic instead of stone").

For Pro mode: spawn a **fresh-context judge subagent** and pass it
the rubric from [references/rubric.md](references/rubric.md). The
judge returns `[composition, lighting, materials, details, total,
gap_list]`. The orchestrator must not write prompts for the worker
that include the judge's own reasoning — that converges the judge
onto itself, not onto the user.

### Step 5 — Iterate (exit criteria)

Stop the loop and ask the user when **any** of these hit:

| Condition | Action |
|---|---|
| Total score ≥ 8, target FPS acceptable | Done — show user the screenshot and ask if more rounds wanted |
| Total score ≥ 8 but FPS unacceptable | Optimize losslessly first, then judge again |
| **Stall approaching**: same gap named 2 rounds in a row, OR best score did not improve by ≥ 1 in 2 rounds | Stop tweaking. Step back: redesign assets, reposition camera, rework lighting. Aim for a dramatic change, not incremental. |
| **Stalled**: a "Stall approaching" dramatic change did not improve score (or regressed) | Stop. Ask the user whether the current state is good enough or whether something is significantly off. |
| User-instructed exit (Plus mode: every 3 rounds mandatory checkpoint) | Stop, present state, ask for direction. |
| None of the above | Continue looping. |

**Do not degrade visual fidelity to hit a time budget.** If the
budget runs out with the scene half-built-but-pretty, that is better
than fully-built-and-ugly. See [references/fps-budget.md](references/fps-budget.md).

## Discipline (always applies)

These rules come from dream-loop and are non-negotiable:

1. **`.blender-loop/` working directory** — store `target.png`,
   `round-N.png`, `state.json`, and any local 3D assets there.
   Add `.blender-loop/` to the project's `.gitignore`.
2. **Fresh context per round** — workers and judges must not see
   prior rounds' reasoning. Use real subagents, not forks.
3. **True subagents in the same thread** — do not create separate
   tasks or threads; subagents within the orchestrator's thread
   inherit the same dispatcher and can call `blender-harness`
   without re-bootstrapping a session.
4. **Never claim "concept art" in the dream prompt** — the target
   is an in-engine screenshot, not an artist's interpretation.
   Words like "concept art", "painting", "cinematic shot" drift
   the target away from what the scene can actually render.
5. **Concrete gap names, not vibes** — the judge's feedback must
   name the specific pixel/material/light difference, with enough
   detail that another agent can fix exactly that.
6. **Maintain prior-round judgment consistency** — if a judge
   gave 6 last round and now gives 5, the score should reflect the
   regression, not flattering-up.
7. **Don't auto-resubmit ambiguous generations** — see
   `blender-harness` for the receipt / unknown-state discipline;
   the same rules apply if you wire `image-factory-run` or
   `dreamina-cli` for the Dream step.
8. **Workflow choice is exclusive** — Plus and Pro are not
   inter-compatible. Pick one at session start and stay there.

## Quick start

When the user says "dream-loop this Blender scene":

```text
1. Ask one question: which tier (Plus / Pro)?
2. Pick the backend for the Dream step (default image-factory-use).
3. Create .blender-loop/ in the working directory.
4. Generate target.png into .blender-loop/.
5. Round 1:
   - Plus: spawn worker subagent → harness mutations → scene.screenshot
   - Pro:  orchestrator or worker → harness mutations → scene.screenshot
   - Plus: orchestrator inspects both PNGs, writes concrete gap list
   - Pro:  spawn fresh-context judge subagent with rubric
6. Evaluate exit criteria. Continue or stop per the table above.
7. Plus mode: after 3 rounds, mandatory checkpoint.
```

## Cross-skill references

This skill does **not** duplicate any other skill's body. Hand off
explicitly by name:

| Need | Hand off to |
|---|---|
| Structured scene commands (transactions, capability maturity) | `blender-harness` |
| Still PNG capture into approved output root | `scene.screenshot` (in `blender-harness`) |
| Image generation for the Dream step | `image-factory-use` or `baoyu-image-gen` |
| Blender design workflow (milestone-based scene build) | `blender-design` |
| Domain-specific scene work (cinematography, hair, sculpt, etc.) | the corresponding upstream `blender-*` skill from `blender-skills` |

Install any of the above with:

```text
npx skills add full-aigc-plugins/blender-design-plugin --skill <skill-name>
npx skills add full-aigc-plugins/image-factory-plugin --skill <image-factory-use>
npx skills add full-aigc-plugins/baoyu-skills --skill <baoyu-image-gen>
```

Do not inline any of their bodies; the install is granular and the
consumer may have only a subset.

## Out of scope

This skill does **not**:

- Implement any Blender private API (use `blender-harness`).
- Embed private credentials or assume any backend.
- Bypass the approved-output-root policy on `scene.screenshot`.
- Mint or substitute the `scene.screenshot` receipt (it is verified
  by `blender-harness` already).
- Treat the judge subagent as a verdict — it is a signal; the user's
  human rejection always wins, even when the model score is perfect
  (same discipline as `image-factory-judge`).
- Run forever — every loop must respect its exit criteria.

## Attribution

The 5-stage loop pattern, the 4-dimension rubric, the "Plus/Pro"
tier split, the "don't degrade for time budget" discipline, and
the "fresh-context judge subagent" discipline are all sourced from
achimala/dream-loop (MIT, © 2026 Anshu Chimala). This skill
**implements the pattern via cross-skill references** rather than
copying dream-loop code. See `research/dream-loop/` for the
upstream source.

<!-- QUALITY_BASELINE_V1 -->
## When to use（什么时候使用）

当用户希望 Blender 场景以**目标图像**为参照进行自动迭代收敛时,加载本技能。摘要:本技能以 dream → build → screenshot → critique → iterate 五阶段闭环,把新上线的 `scene.screenshot` 捕获与 `blender-harness` JSON 命令以及独立上下文的视觉评分 judge 子代理组合起来,实现「接近目标视觉」的迭代收敛。

## Rules

- 先读后写:启动循环前确认目标图存在、授权路径已设、harness 会话已就绪。
- 权限最小化:每次只跑一个 round;Plus 模式 3 轮后必须停下来问用户。
- 证据优先:每一轮的产物必须带 sha256 收据,不允许凭肉眼声称成功。
- 幂等优先:不修改既有 round 的 PNG,后续 round 写到 round-N+1.png。
- 隐私安全:不把用户的目标图(或 LLM 评分)外发到训练或检索 API。

## Workflow

### Step 1:澄清意图

确认本技能匹配目标;否则交给更精确的技能(单图渲染就交给 `blender-harness` 或 `blender-design`)。
### Step 2:执行预检

确认 Plus/Pro tier、目标图存在、`.blender-loop/` 已建、`scene.screenshot` 可用;任一关键条件未知时停止在只读阶段。
### Step 3:形成计划

列出将调用的工具(`scene.screenshot`、`blender-harness`、可选 `image-factory-use`)、轮次上限、退出准则、失败回退方式。
### Step 4:执行动作

按 5 阶段循环;每轮记录证据(sha256 收据 + 具体 gap 列表);每个外部调用均保留可关联的状态或回执。
### Step 5:验证交付

把最终的 `.blender-loop/round-N.png` 与 `target.png` 一并展示,给出 judge 评分与剩余 gap,标明实际运行层级与未完成项。

## Validation checklist

- `target.png` 与每轮 `round-N.png` 都存在,每张 PNG 都带 sha256 收据。
- judge 反馈是具体可执行 gap 列表,不是「不够好」之类的笼统语言。
- 退出条件命中,用户被明确告知而不是「做完自动停了」。
- 工作目录 `.blender-loop/` 已在 `.gitignore`。

## Gotchas

1. **把计划当结果**:生成目标图不等于真的迭代过场景。
2. **隐式扩大范围**:Pro 模式下 judge 子代理可能提出大改,先确认用户预算再行动。
3. **版本漂移**:本 skill 依赖 `scene.screenshot`(L1),如果上游 harness 改动协议,需同步更新。
4. **证据过期**:目标图与最近 round 之间可能跨越多次 harness 重启,确认产物 sha 与当前会话绑定。

## 不适用与边界

不修改用户已有的 `.blend` 文件结构(只用 harness 事务);不在多用户共享目录运行(避免 round-N.png 冲突)。如果请求需要别的技能,不复制其正文;按技能名称进行交接。

## Progressive disclosure

- 想要分轮细节与「stall approaching」判断逻辑,读 `references/workflow.md`。
- 想要 4 维评分语言与总分计算,读 `references/rubric.md`。
- 想要 3D 资产(Fal H3.1/Trellis)批量生成指南,读 `references/assets-3d.md`。
- 想要「不因时间预算降低视觉质量」的具体纪律,读 `references/fps-budget.md`。
- 想要完整 Plus 工作流示例,读 `examples/plus-workflow.md`;想要 Pro 工作流示例,读 `examples/pro-workflow.md`。