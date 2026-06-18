#!/usr/bin/env python3
"""检查入口文档是否回填易漂移运行时快照。

当前只约束 3 个入口文档:
  - AGENTS.md
  - .omo/INDEX.md
  - docs/PANORAMA.md

目标:
  - 这些文档只能保留架构骨架、导航和 SSOT 指针
  - 不应重新写入健康分 / 运行时 Phase / 测试统计 / 通过率等快照
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

TARGETS = (
    WORKSPACE / "AGENTS.md",
    WORKSPACE / ".omo" / "INDEX.md",
    WORKSPACE / "docs" / "PANORAMA.md",
)

RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("禁止健康分快照", re.compile(r"健康分\s*[:：]\s*\d")),
    ("禁止 code_freeze 快照", re.compile(r"code_freeze\s*[:：]\s*(true|false)", re.IGNORECASE)),
    ("禁止运行时 Phase 快照", re.compile(r"当前\s*Phase\s*[:：]\s*\d+", re.IGNORECASE)),
    ("禁止测试通过率快照", re.compile(r"\b\d+(?:\.\d+)?%\b")),
    ("禁止 tests 数量快照", re.compile(r"\b\d[\d,~+]*\s+tests?\b", re.IGNORECASE)),
    ("禁止 passed 数量快照", re.compile(r"\b\d[\d,~+]*\s+passed\b", re.IGNORECASE)),
    ("禁止 routes 数量快照", re.compile(r"\b\d[\d,~+]*\s+routes?\b", re.IGNORECASE)),
    ("禁止 collected/passed 快照", re.compile(r"\b\d+\s+collected\s*/\s*\d+\s+passed\b", re.IGNORECASE)),
)


def main() -> int:
    violations = 0
    for path in TARGETS:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for label, pattern in RULES:
                if pattern.search(line):
                    print(f"{path.relative_to(WORKSPACE)}:{lineno}: {label}: {line.strip()}")
                    violations += 1
    if violations:
        print(f"doc-ssot-snapshot-check: FAIL ({violations} violations)")
        return 1
    print("doc-ssot-snapshot-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
