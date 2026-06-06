#!/usr/bin/env python3
"""依赖检查 (CI script).

检查跨层 import 违规:
  - cockpit 不能 import kairon.xxx (应通过 Agora)
  - kairon 不能 import cockpit (向上依赖)
  - ecos 不能 import kairon (应由 kairon 调 ecos)
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

# ── 违规规则 ────────────────────────────────────────────

VIOLATION_RULES = [
    # (源项目, 目标包前缀, 说明)
    ("cockpit", "kairon", "L3 cockpit 不能 import L2 kairon (应通过 Agora MCP)"),
    ("agora", "cockpit", "I0 agora 不能 import L3 cockpit (向上依赖)"),
    ("ecos", "kairon", "L0 ecos 不能 import L2 kairon (应由 kairon 调 ecos)"),
    ("omo", "kairon", "L2 omo 不能 import L2 kairon (应通过 Agora) — 除了 omo.omo_i0"),
]


def check_cross_deps() -> int:
    """检查跨层 import 违规。"""
    violations = 0
    project_roots = {
        p.name: p
        for p in WORKSPACE.glob("projects/*")
        if p.is_dir() and not p.name.startswith("_")
    }

    for proj_name, proj_root in project_roots.items():
        if proj_name not in {"cockpit", "agora", "ecos", "omo"}:
            continue

        src_dir = proj_root / "src"
        if not src_dir.is_dir():
            continue

        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                for line in py_file.read_text(encoding="utf-8").split("\n"):
                    if line.strip().startswith("#"):
                        continue
                    for rule_src, rule_target, rule_desc in VIOLATION_RULES:
                        if proj_name != rule_src:
                            continue
                        if f"from {rule_target}." in line or f"import {rule_target}." in line:
                            violations += 1
                            rel = py_file.relative_to(WORKSPACE)
                            print(f"  ❌ {rel}: {line.strip()}")
                            print(f"     → 违反: {rule_desc}")
            except Exception:
                pass

    return violations


def main() -> int:
    print("🔍 检查跨层 import 违规...")
    violations = check_cross_deps()
    print(f"   违规: {'✅ 无' if violations == 0 else f'❌ {violations} violations'}")
    return 0 if violations == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
