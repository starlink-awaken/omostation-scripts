#!/usr/bin/env python3
"""检查 PANORAMA.md 是否保持为项目级架构文档总索引。

当前约束:
1. PANORAMA.md 必须存在“项目级架构文档索引”段落
2. 该段落中列出的 active 项目，其 ARCHITECTURE/CALLCHAIN/BOUNDARY 文档必须存在
3. archived 项目必须明确写 archived/并入说明，而不是继续冒充 active
"""

from __future__ import annotations

import re

from lib.bootstrap import workspace_root

WORKSPACE = workspace_root()
PANORAMA = WORKSPACE / "docs" / "PANORAMA.md"

ACTIVE_PROJECTS = (
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

ARCHIVED_MARKERS = ("ARCHIVED", "已并入", "快照在 `/_archived/")


def main() -> int:
    text = PANORAMA.read_text(encoding="utf-8")
    appendix_marker = "## 附录：项目级架构文档索引"
    if appendix_marker not in text:
        print("docs/PANORAMA.md: missing project architecture appendix")
        return 1
    appendix_text = text.split(appendix_marker, 1)[1]

    violations = 0
    for project in ACTIVE_PROJECTS:
        row_pattern = re.compile(rf"^\|\s*{re.escape(project)}\s*\|.*$", re.MULTILINE)
        match = row_pattern.search(appendix_text)
        if not match:
            print(f"docs/PANORAMA.md: missing active project row: {project}")
            violations += 1
            continue
        row = match.group(0)
        if "ARCHITECTURE.md" not in row or "CALLCHAIN.md" not in row or "BOUNDARY.md" not in row:
            print(f"docs/PANORAMA.md: incomplete architecture links for: {project}")
            violations += 1
        for doc in ("ARCHITECTURE.md", "CALLCHAIN.md", "BOUNDARY.md"):
            path = WORKSPACE / "projects" / project / doc
            if not path.exists():
                print(f"missing project doc: {path.relative_to(WORKSPACE)}")
                violations += 1

    archived_projects = ("aetherforge-swarm-ext", "compute-mesh", "llm-gateway", "swarm-engine")
    for project in archived_projects:
        row_pattern = re.compile(rf"^\|\s*{re.escape(project)}\s*\|.*$", re.MULTILINE)
        match = row_pattern.search(appendix_text)
        if not match:
            print(f"docs/PANORAMA.md: missing archived project row: {project}")
            violations += 1
            continue
        row = match.group(0)
        if not any(marker in row for marker in ARCHIVED_MARKERS):
            print(f"docs/PANORAMA.md: archived project row lacks archived marker: {project}")
            violations += 1

    if violations:
        print(f"panorama-arch-links: FAIL ({violations} violations)")
        return 1
    print("panorama-arch-links: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
