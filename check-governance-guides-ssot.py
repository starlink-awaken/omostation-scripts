#!/usr/bin/env python3
"""检查 governance 指南是否保持为稳定说明而非静态阈值面板。"""

from __future__ import annotations

from lib.bootstrap import workspace_root

WORKSPACE = workspace_root()

TARGETS = {
    ".omo/_knowledge/governance/README.md": (
        "不维护健康度阈值、实时状态、工具覆盖率或阶段性命令清单",
        "/.omo/standards/omo-governance-surfaces.md",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
        "/.omo/debt/",
    ),
    ".omo/_knowledge/governance/quickstart.md": (
        "不维护健康度阈值、固定 make 命令矩阵或静态 SLA 数字",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
        "/.omo/debt/",
        "make governance-verify",
        "cockpit status",
    ),
    ".omo/_knowledge/governance/sla.md": (
        "不再把具体数值阈值当作跨阶段永恒 SSOT",
        "/.omo/state/system.yaml",
    ),
}

FORBIDDEN = {
    ".omo/_knowledge/governance/quickstart.md": (
        "debt_weight | 债务权重 (0-1) | ≥ 0.9",
        "debt_health | 健康度 (0-100) | ≥ 90",
        "resolved_rate | 解决率 | ≥ 90%",
        "make debt-check",
        "make debt-audit",
        "make governance-dashboard",
    ),
    ".omo/_knowledge/governance/sla.md": (
        "| debt_weight | ≥ 0.9 |",
        "| debt_health | ≥ 90 |",
        "| resolved_rate | ≥ 90% |",
        "| critical | 1 小时 | 24 小时 |",
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
                violations.append(f"{rel}: forbidden stale guidance `{needle}`")

    if violations:
        for violation in violations:
            print(violation)
        print(f"governance-guides-ssot: FAIL ({len(violations)} violations)")
        return 1

    print("governance-guides-ssot: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
