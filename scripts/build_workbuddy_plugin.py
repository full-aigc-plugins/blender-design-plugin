#!/usr/bin/env python3
"""Assemble the WorkBuddy team plugin from this repository.

Single source of truth lives in ``workbuddy/`` (agents, skills) plus the
production tree (scripts/bin/config/schemas and the 26 Codex skills that are
vendored as production references).  The assembled, self-contained plugin is
written to ``dist/workbuddy/`` as a directory marketplace:

    dist/workbuddy/
      .codebuddy-plugin/marketplace.json
      plugins/blender-production-team/
        .codebuddy-plugin/plugin.json
        agents/*.md
        avatars/*.png            (generated, no external deps)
        skills/blender-harness/SKILL.md
        skills/blender-production/{SKILL.md,references/*.md}
        scripts/ bin/ config/ schemas/   (vendored, minus __pycache__)
        LICENSE THIRD_PARTY_NOTICES.md

Run:  python3 scripts/build_workbuddy_plugin.py [--out dist/workbuddy]
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "workbuddy"

MARKETPLACE = "partme-blender"
PLUGIN_NAME = "blender-production-team"
VERSION = "0.1.0"

MEMBERS = [
    # id, zh name, en name, zh profession, en profession, avatar colour
    ("blender-team-lead", "岚一", "Lan", "3D 生产总监", "3D Production Director", "#1D4ED8"),
    ("blender-modeler", "塑岩", "Suyan", "3D 建模师", "3D Modeler", "#C2410C"),
    ("blender-rigger-animator", "骨风", "Gufeng", "角色绑定动画师", "Character TD / Animator", "#6D28D9"),
    ("blender-lookdev-renderer", "彩澜", "Cailan", "材质灯光渲染师", "Lookdev / Lighting Artist", "#BE185D"),
    ("blender-effects-editor", "影流", "Yingliu", "特效剪辑师", "FX / Editorial Artist", "#047857"),
    ("blender-qc-delivery", "核真", "Hezhen", "质检交付工程师", "QC / Pipeline Engineer", "#334155"),
]


def _solid_png(path: Path, colour: str, size: int = 128) -> None:
    """Write a minimal solid-colour PNG (no external dependencies)."""
    rgb = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
    raw = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


def _copy_tree(src: Path, dst: Path) -> int:
    count = 0
    for item in src.rglob("*"):
        if any(part in {"__pycache__", ".DS_Store"} for part in item.parts):
            continue
        target = dst / item.relative_to(src)
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        count += 1
    return count


def build(out_dir: Path) -> dict:
    plugin_dir = out_dir / "plugins" / PLUGIN_NAME
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # agents
    n_agents = _copy_tree(SRC / "agents", plugin_dir / "agents")

    # skills: harness verbatim; production SKILL.md + the 26 repo skills as references
    _copy_tree(SRC / "skills" / "blender-harness", plugin_dir / "skills" / "blender-harness")
    prod_dir = plugin_dir / "skills" / "blender-production"
    prod_dir.mkdir(parents=True)
    shutil.copy2(SRC / "skills" / "blender-production" / "SKILL.md", prod_dir / "SKILL.md")
    refs = prod_dir / "references"
    refs.mkdir()
    n_refs = 0
    for skill_dir in sorted((ROOT / "skills").iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.is_file():
            shutil.copy2(skill_md, refs / f"{skill_dir.name}.md")
            n_refs += 1

    # vendored execution surface
    n_scripts = _copy_tree(ROOT / "scripts", plugin_dir / "scripts")
    n_bin = _copy_tree(ROOT / "bin", plugin_dir / "bin")
    n_config = _copy_tree(ROOT / "config", plugin_dir / "config")
    n_schemas = _copy_tree(ROOT / "schemas", plugin_dir / "schemas")
    for licence in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        if (ROOT / licence).is_file():
            shutil.copy2(ROOT / licence, plugin_dir / licence)

    # avatars
    avatars = plugin_dir / "avatars"
    avatars.mkdir()
    _solid_png(avatars / "team.png", "#0F172A")
    for member_id, _, _, _, _, colour in MEMBERS:
        _solid_png(avatars / f"{member_id}.png", colour)

    # plugin manifest (shape mirrors the ai-content-creator-team reference plugin)
    members_field = []
    for member_id, zh, en, zh_prof, en_prof, _ in MEMBERS:
        entry = {
            "id": member_id,
            "name": {"en": en, "zh": zh},
            "profession": {"en": en_prof, "zh": zh_prof},
            "avatar": f"avatars/{member_id}.png",
        }
        entry["role"] = "lead" if member_id == "blender-team-lead" else "member"
        members_field.append(entry)
    manifest = {
        "name": PLUGIN_NAME,
        "version": VERSION,
        "description": "Blender 3D production team driving the codex-blender harness: modeling, "
                       "rigging/animation, lookdev/rendering, effects/editorial and QC/delivery, "
                       "with receipt-verified acceptance.",
        "author": {"name": "partme-ai"},
        "agents": [f"./agents/{m[0]}.md" for m in MEMBERS],
        "skills": ["./skills/blender-harness", "./skills/blender-production"],
        "expertType": "team",
        "agentName": "blender-team-lead",
        "teamInfo": {
            "leadAgent": "blender-team-lead",
            "memberAgents": [m[0] for m in MEMBERS[1:]],
        },
        "displayName": {"en": "Blender Production Team", "zh": "Blender 3D 生产专家团"},
        "profession": {"en": "Blender Production Team", "zh": "Blender 3D 生产专家团"},
        "displayDescription": {
            "en": "Structured Blender production team: launch a managed harness session, dispatch "
                  "closed-contract commands, and deliver receipt-verified models, animations, renders "
                  "and video.",
            "zh": "结构化 Blender 生产团队：启动托管 harness 会话，派发闭合契约命令，交付经回执核验的模型、动画、渲染与视频。",
        },
        "avatar": "avatars/team.png",
        "categoryId": "01-ProductDesign",
        "defaultInitPrompt": {
            "en": "Launch a Blender harness session and model a desk speaker, then export a verified GLB.",
            "zh": "启动 Blender 会话，建一个桌面音箱模型并导出经验证的 GLB。",
        },
        "quickPrompts": [
            {"en": "Model a hard-surface product and export verified GLB/FBX",
             "zh": "建一个硬表面产品件并导出经验证的 GLB/FBX"},
            {"en": "Rig a character, validate deformation, render a turntable",
             "zh": "绑定角色、做变形验证并渲染转台"},
            {"en": "Edit a sequence in VSE and export H.264/AAC with media verification",
             "zh": "在 VSE 剪辑序列并导出通过媒体校验的 H.264/AAC"},
        ],
        "tags": [
            {"en": "Blender", "zh": "Blender"},
            {"en": "3D Production", "zh": "3D 生产"},
            {"en": "Receipt-Verified Delivery", "zh": "回执核验交付"},
        ],
        "members": members_field,
    }
    meta = plugin_dir / ".codebuddy-plugin"
    meta.mkdir()
    (meta / "plugin.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")

    # directory marketplace manifest
    market_meta = out_dir / ".codebuddy-plugin"
    market_meta.mkdir()
    (market_meta / "marketplace.json").write_text(json.dumps({
        "name": MARKETPLACE,
        "description": "partme-ai local plugin marketplace (auto-generated by build_workbuddy_plugin.py)",
        "plugins": [{
            "name": PLUGIN_NAME,
            "source": f"./plugins/{PLUGIN_NAME}",
            "description": manifest["description"],
        }],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "out": str(out_dir),
        "agents": n_agents,
        "skillReferences": n_refs,
        "scripts": n_scripts,
        "bin": n_bin,
        "config": n_config,
        "schemas": n_schemas,
        "members": len(MEMBERS),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assemble the WorkBuddy team plugin")
    parser.add_argument("--out", default=str(ROOT / "dist" / "workbuddy"))
    args = parser.parse_args(argv)
    summary = build(Path(args.out).resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
