#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

TARGETS = {
    ".omo/_knowledge/design/plans/agent-architecture-audit-redteam.md": (
        "历史审计与红队分析输入",
        "不是当前 Agent 拓扑、当前协作面或当前运行状态 SSOT",
    ),
    ".omo/_knowledge/design/plans/beyond-phase4-review.md": (
        "历史远景审查输入",
        "不是当前能力边界、当前系统现状或当前路线图 SSOT",
    ),
    ".omo/_knowledge/design/plans/deep-architecture-agent-analysis.md": (
        "历史架构分析输入",
        "不是当前 Agent 实现状态、工具计数或当前入口拓扑 SSOT",
    ),
    ".omo/_knowledge/design/plans/evolution-roadmap-4phases.md": (
        "历史路线图输入",
        "不是当前项目清单、当前能力计数或当前健康分 SSOT",
    ),
    ".omo/_knowledge/design/plans/l0-l1-l4-state-bridge-design.md": (
        "历史设计提案",
        "不是当前 runtime/治理状态分工的唯一实现真相",
    ),
    ".omo/_knowledge/design/sharedbrain-decomposition-architecture.md": (
        "历史拆解分析输入",
        "不是当前 SharedBrain / kairon 边界、当前项目状态或当前债务 SSOT",
    ),
    ".omo/_knowledge/design/plans/phase17-wave1-sharedbrain-decomposition-plan.md": (
        "历史阶段的实施计划输入",
        "不是当前 active task、当前阶段状态或当前 SharedBrain 处理策略 SSOT",
    ),
}


def main() -> int:
    errors: list[str] = []
    for rel, needles in TARGETS.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"{rel}: missing `{needle}`")

    if errors:
        print("FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("PASS: design body docs with high snapshot risk are explicitly marked historical/reference")
    return 0


if __name__ == "__main__":
    sys.exit(main())
