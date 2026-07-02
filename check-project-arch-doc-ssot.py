#!/usr/bin/env python3
"""检查项目级 ARCHITECTURE.md 头部是否遵守 SSOT 约束。

目标:
1. active 项目的 ARCHITECTURE.md 必须显式声明 `> **SSOT**:`
2. `> **Health**:` 只能给出指针式说明, 不能回填数值型运行时快照
3. 头部前若干行不得重新写入 tests / routes / tools / pass rate 等漂移事实
"""

from __future__ import annotations

import re

from lib.bootstrap import workspace_root

WORKSPACE = workspace_root()

PROJECTS = (
    "agora",
    "cockpit",
    "kairon",
    "gbrain",
    "omo",
    "metaos",
    "runtime",
    "ecos",
    "aetherforge",
    "bus-foundation",
    "c2g",
    "family-hub",
    "l4-kernel",
    "model-driven",
    "observability",
    "omo-debt",
)

SNAPSHOT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("禁止百分比快照", re.compile(r"\b\d+(?:\.\d+)?%\b")),
    ("禁止 tests 数量快照", re.compile(r"\b\d[\d,~+]*\s+tests?\b", re.IGNORECASE)),
    ("禁止 passed 数量快照", re.compile(r"\b\d[\d,~+]*\s+passed\b", re.IGNORECASE)),
    ("禁止 routes 数量快照", re.compile(r"\b\d[\d,~+]*\s+routes?\b", re.IGNORECASE)),
    ("禁止 tools 数量快照", re.compile(r"\b\d[\d,~+]*\s+tools?\b", re.IGNORECASE)),
    ("禁止 MCP 数量快照", re.compile(r"\b\d[\d,~+]*\s+MCP\b", re.IGNORECASE)),
)


def main() -> int:
    violations: list[str] = []

    for project in PROJECTS:
        path = WORKSPACE / "projects" / project / "ARCHITECTURE.md"
        if not path.exists():
            violations.append(f"missing doc: {path.relative_to(WORKSPACE)}")
            continue

        lines = path.read_text(encoding="utf-8").splitlines()
        header = lines[:12]

        health_line = next((line for line in header if line.startswith("> **Health**:")), None)
        ssot_line = next((line for line in header if line.startswith("> **SSOT**:")), None)

        if health_line is None:
            violations.append(f"{path.relative_to(WORKSPACE)}: missing `> **Health**:` header")
        if ssot_line is None:
            violations.append(f"{path.relative_to(WORKSPACE)}: missing `> **SSOT**:` header")

        for lineno, line in enumerate(header, start=1):
            for label, pattern in SNAPSHOT_RULES:
                if pattern.search(line):
                    violations.append(f"{path.relative_to(WORKSPACE)}:{lineno}: {label}: {line.strip()}")

    if violations:
        for violation in violations:
            print(violation)
        print(f"project-arch-doc-ssot: FAIL ({len(violations)} violations)")
        return 1

    print("project-arch-doc-ssot: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
