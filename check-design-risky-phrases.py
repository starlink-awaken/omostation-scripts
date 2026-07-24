#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from lib.bootstrap import workspace_root

ROOT = workspace_root()
DESIGN_ROOT = ROOT / ".omo/_knowledge/design"

RISKY_PHRASES = (
    "当前状态",
    "健康分",
    "MCP tools",
    "活跃项目",
    "Raw Health",
    "Effective Health",
    "项目现状",
)

HISTORICAL_MARKERS = (
    "历史阶段",
    "历史规划输入",
    "历史设计输入",
    "历史拆解分析输入",
    "历史路线图输入",
    "历史提案草案",
    "历史认知输入",
    "历史审计",
    "历史架构分析输入",
    "历史远景审查输入",
    "历史阶段的兼容性契约记录",
    "历史红队修订补丁",
    "historical",
    "reference",
    "不是当前",
)

EXCLUDED_DIRS = {"history", "archive", "diagrams", "reviews"}


def is_excluded(rel: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in rel.parts)


def has_risky_phrase(text: str) -> bool:
    return any(needle in text for needle in RISKY_PHRASES)


def has_historical_marker(text: str) -> bool:
    return any(marker in text for marker in HISTORICAL_MARKERS)


def main() -> int:
    violations: list[str] = []
    for path in sorted(DESIGN_ROOT.rglob("*.md")):
        rel = path.relative_to(DESIGN_ROOT)
        if is_excluded(rel):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if has_risky_phrase(text) and not has_historical_marker(text):
            hits = [needle for needle in RISKY_PHRASES if needle in text]
            violations.append(
                f"{rel}: risky snapshot phrases without explicit historical/reference boundary: {', '.join(hits)}"
            )

    if violations:
        print("FAIL")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("PASS: risky snapshot phrases in design docs are guarded by historical/reference boundaries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
