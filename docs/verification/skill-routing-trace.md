# Skill routing TRACE review

Scope: 26 distributed Blender Design Skills after precise-routing remediation. This evaluates the plugin Skill system and each changed Skill's trigger/safety text; it does not substitute for Blender runtime evidence.

## T — Trust

- Command catalog exposes exact Skill names, availability, maturity and evidence; unsupported Rigify remains unavailable.
- Router and domain Skills preserve asset, overwrite, extension-install, external-action and paid-action boundaries.
- Names and responsibilities do not imply access to user accounts or external systems.

Result: PASS for operational trust. English is retained to match adjacent Codex Maya/Dreamina plugin conventions; Chinese user responses remain required by the router.

## R — Reliability

- Missing editor, stale selection/revision, interrupted jobs, missing assets/extensions and failed milestones have explicit stopping or recovery routes.
- Background jobs declare snapshot binding, cancellation, no automatic retry, explicit frame-only resume, immutable manifest binding and separate composition.
- Runtime evidence is stage-specific rather than copied from P1.

Result: PASS.

## A — Adaptability

- Command-level mapping takes precedence over domain fallback; multi-domain recipes retain multiple Skills.
- `job.submit.kind` has explicit conditional routing for EXPORT, RENDER_STILL, RENDER_ANIMATION_FRAMES, COMPOSE_VIDEO and BAKE_POINT_CACHES.
- Eight formerly ambiguous concerns have distinct Skill names: cinematography, quality validation, background jobs, sculpt surface, hair, simulation, tracking and sequence editing.

Result: PASS.

## C — Convention

- All names use lowercase `codex-blender-<action-or-domain>`, under 64 characters, with matching folder/frontmatter.
- Progressive disclosure is router → domain Skill → shared routing reference; narrow Skills remain concise.
- Generic FAQ quotas from the TRACE template were intentionally not copied into every Skill because duplicate user documentation would weaken Agent Skill context hygiene. This exception follows the installed skill-creator guidance.

Result: PASS with documented framework adaptation; no artificial 5.0 numeric score is claimed.

## E — Effectiveness

- `tests/test_skill_routing.py` verifies lifecycle, command-level, multi-Skill, conditional-job, evidence and role mappings.
- `capability.list` in Blender 5.2.1 reports 26 distributed Skills, 22 command-referenced Skills and four valid orchestration-only Skills.
- P8 adds real behavior evidence for durable PNG/multilayer EXR sequences, explicit missing-frame recovery, independent FFmpeg composition, extended VSE sources and Blender 5.2 compositor modifiers.

Result: PASS.

Overall: release-routing gate passed after real catalog generation and behavior tests. This report does not claim Windows L4 or installed-cache validation.
