#!/usr/bin/env python3
"""检查当前治理总纲文档是否回避运行时快照。"""

from __future__ import annotations

import re

from lib.bootstrap import workspace_root

WORKSPACE = workspace_root()

TARGETS = {
    ".omo/_truth/governance-charter-v1.md": (
        "不再维护项目计数、测试数、MCP/CLI 数、端口活跃状态、阶段完成度等运行时快照",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
    ".omo/_knowledge/management/governance-master-index.md": (
        "不维护运行时计数/健康分快照",
        "/.omo/standards/omo-governance-surfaces.md",
        "/.omo/state/system.yaml",
    ),
    ".omo/_knowledge/management/governance-charter-v1.md": (
        "不维护项目数、包数、测试数、阶段完成度等运行时快照",
        "全工作区项目",
    ),
}

FORBIDDEN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("禁止 packages 快照", re.compile(r"\b\d+\s+packages?\b", re.IGNORECASE)),
    ("禁止 MCP 数量快照", re.compile(r"(?<![.\d])\b\d+\s+MCP(?:\s+tools?)?\b", re.IGNORECASE)),
    ("禁止 tests 数量快照", re.compile(r"\b\d+\s+tests?\b", re.IGNORECASE)),
    ("禁止项目计数快照", re.compile(r"\b\d+\s+项目\b")),
    ("禁止 CLI/MCP/HTTP 数量快照", re.compile(r"CLI\s+\d+|MCP\s+\d+|HTTP\s+\d+", re.IGNORECASE)),
    ("禁止 X4 Score 快照", re.compile(r"X4 Score\s+\d+", re.IGNORECASE)),
)


def main() -> int:
    violations: list[str] = []
    for rel, needles in TARGETS.items():
        text = (WORKSPACE / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                violations.append(f"{rel}: missing `{needle}`")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in FORBIDDEN_RULES:
                if pattern.search(line):
                    violations.append(f"{rel}:{lineno}: {label}: {line.strip()}")

    if violations:
        for violation in violations:
            print(violation)
        print(f"governance-doc-ssot: FAIL ({len(violations)} violations)")
        return 1

    print("governance-doc-ssot: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
