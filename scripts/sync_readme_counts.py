"""Sync the bilingual README capability-count lines from docs/verification/capability-counts.json.

Run after adding commands or skills:
    python3 scripts/sync_readme_counts.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTS = json.loads((ROOT / "docs/verification/capability-counts.json").read_text(encoding="utf-8"))


def numbers(mode):
    commands = COUNTS[mode]["commands"]
    skills = COUNTS[mode]["skills"]
    return {
        "total": commands["total"], "l3": commands["L3"], "l4": commands["L4"],
        "l1": commands["L1"], "l2": commands["L2"], "domains": COUNTS[mode]["domains"]["total"],
        "onDisk": skills["onDisk"], "referenced": skills["referenced"],
    }


def rewrite_line(line, managed, connector):
    if re.match(r"- \*\*Managed\*\* registers \d+ commands:", line):
        m = managed
        return (f"- **Managed** registers {m['total']} commands: {m['l3']} at L3, "
                f"{m['l4']} Windows-verified recovery and Rigify commands at L4, "
                f"{m['l1']} at L1, and {m['l2']} at L2, across {m['domains']} domains, "
                f"routed through {m['referenced']} of the {m['onDisk']} bundled Skills.")
    if re.match(r"- \*\*Connector\*\* adds the 5 optional", line):
        c = connector
        return (f"- **Connector** adds the 5 optional `official_uploader.*` commands: "
                f"{c['total']} commands, {c['l3']} at L3, {c['l4']} at L4, {c['l1']} at L1, "
                f"and {c['l2']} at L2, across {c['domains']} domains, "
                f"routed through {c['referenced']} Skills.")
    if re.match(r"- \*\*非侵入模式（Managed）\*\* 注册", line):
        m = managed
        return (f"- **非侵入模式（Managed）** 注册 {m['total']} 条命令：其中 {m['l3']} 条 L3、"
                f"{m['l4']} 条经 Windows 验证的恢复与 Rigify 命令达到 L4、{m['l1']} 条 L1、"
                f"0 条 L2，横跨 {m['domains']} 个域，路由到 {m['onDisk']} 个内置 Skill 中的 "
                f"{m['referenced']} 个。")
    if re.match(r"- \*\*Connector 模式\*\* 额外加入", line):
        c = connector
        return (f"- **Connector 模式** 额外加入 5 条可选 `official_uploader.*` 命令："
                f"合计 {c['total']} 条命令，{c['l3']} 条 L3、{c['l4']} 条 L4、{c['l1']} 条 L1、"
                f"0 条 L2，横跨 {c['domains']} 个域，路由到 {c['referenced']} 个 Skill。")
    return line


def sync(path):
    text = path.read_text(encoding="utf-8")
    managed, connector = numbers("managed"), numbers("connector")
    lines = [rewrite_line(line, managed, connector) for line in text.splitlines()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    for name in ("README.md", "README.zh-CN.md"):
        readme = ROOT / name
        if readme.exists():
            sync(readme)
            print(f"synced {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
