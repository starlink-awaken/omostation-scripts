#!/usr/bin/env python3
"""检查治理机制/注册表文档是否仍在维护运行时快照。"""

from __future__ import annotations

from pathlib import Path

from lib.bootstrap import workspace_root

WORKSPACE = workspace_root()

TARGETS = {
    ".omo/_knowledge/management/governance-mechanism.md": (
        "不维护当前 Phase、下次审查时间、服务数量、债务数量、交付物数量等运行时快照",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
        "/.omo/debt/",
        "/.omo/_delivery/",
    ),
    ".omo/_knowledge/management/x-axis-implementation-registry.md": (
        "本文不再手工维护实现状态",
        "probe 探活声明",
    ),
}

FORBIDDEN = {
    ".omo/_knowledge/management/governance-mechanism.md": (
        "Phase: 28 W4",
        "下次审查:",
        "96 项",
        "89 项",
        "71+ 交付物",
        "12 服务",
    ),
    ".omo/_knowledge/management/x-axis-implementation-registry.md": (
        "× 7 项目",
    ),
}


def main() -> int:
    violations: list[str] = []
    for rel, needles in TARGETS.items():
        text = (WORKSPACE / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                violations.append(f"{rel}: missing `{needle}`")
        for needle in FORBIDDEN.get(rel, ()):
            if needle in text:
                violations.append(f"{rel}: forbidden stale snapshot text `{needle}`")

    if violations:
        for violation in violations:
            print(violation)
        print(f"governance-mechanism-ssot: FAIL ({len(violations)} violations)")
        return 1

    print("governance-mechanism-ssot: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
