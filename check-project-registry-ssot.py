#!/usr/bin/env python3
"""检查 .omo/PROJECTS.yaml 的 SSOT 口径。

目标:
1. 关键项目状态与入口文档一致
2. PROJECTS.yaml 只记录稳定身份，不回填测试数/工具数/路由数等运行时快照
3. 特殊项目口径固定:
   - agora-dashboard = archived historical snapshot
   - hermes-console = active mounted console
"""

from __future__ import annotations

import re
from pathlib import Path

from lib.bootstrap import workspace_root

WORKSPACE = workspace_root()
PROJECTS = WORKSPACE / ".omo" / "PROJECTS.yaml"
AGENTS = WORKSPACE / "AGENTS.md"
PANORAMA = WORKSPACE / "docs" / "PANORAMA.md"

SNAPSHOT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("禁止百分比快照", re.compile(r"\b\d+(?:\.\d+)?%\b")),
    ("禁止 tests 数量快照", re.compile(r"\b\d[\d,~+]*\s+tests?\b", re.IGNORECASE)),
    ("禁止 passed 数量快照", re.compile(r"\b\d[\d,~+]*\s+passed\b", re.IGNORECASE)),
    ("禁止 routes 数量快照", re.compile(r"\b\d[\d,~+]*\s+routes?\b", re.IGNORECASE)),
    ("禁止 tools 数量快照", re.compile(r"\b\d[\d,~+]*\s+tools?\b", re.IGNORECASE)),
    ("禁止 MCP 数量快照", re.compile(r"\b\d[\d,~+]*\s+MCP\b", re.IGNORECASE)),
)


def _find_project_status(text: str, name: str) -> str | None:
    pattern = re.compile(
        rf"^  {re.escape(name)}:\n(?:    .*\n)*?    status: ([^\n]+)$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _find_project_desc(text: str, name: str) -> str | None:
    pattern = re.compile(
        rf"^  {re.escape(name)}:\n(?:    .*\n)*?    desc: \"([^\"]+)\"$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def main() -> int:
    violations: list[str] = []

    projects_text = PROJECTS.read_text(encoding="utf-8")
    agents_text = AGENTS.read_text(encoding="utf-8")
    panorama_text = PANORAMA.read_text(encoding="utf-8")

    expected_status = {
        "agora-dashboard": "archived",
        "hermes-console": "active",
    }
    for project, status in expected_status.items():
        actual = _find_project_status(projects_text, project)
        if actual != status:
            violations.append(f".omo/PROJECTS.yaml: `{project}` status expected `{status}`, got `{actual}`")

    expected_desc_needles = {
        "agora-dashboard": "历史快照",
        "hermes-console": "挂载到 cockpit /hermes/*",
    }
    for project, needle in expected_desc_needles.items():
        desc = _find_project_desc(projects_text, project)
        if desc is None or needle not in desc:
            violations.append(f".omo/PROJECTS.yaml: `{project}` desc missing `{needle}`")

    for lineno, line in enumerate(projects_text.splitlines(), start=1):
        if 'desc: "' not in line:
            continue
        for label, pattern in SNAPSHOT_RULES:
            if pattern.search(line):
                violations.append(f".omo/PROJECTS.yaml:{lineno}: {label}: {line.strip()}")

    if "agora-dashboard 独立入口已收敛" not in agents_text:
        violations.append("AGENTS.md: missing agora-dashboard legacy convergence statement")
    if "hermes-console 与 dashboard_server 作为子应用挂载" not in agents_text:
        violations.append("AGENTS.md: missing hermes-console mounted statement")
    if "**LEGACY SNAPSHOT**" not in panorama_text or "agora-dashboard" not in panorama_text:
        violations.append("docs/PANORAMA.md: missing agora-dashboard legacy snapshot row")
    if "projects/hermes-console/ARCHITECTURE.md" not in panorama_text:
        violations.append("docs/PANORAMA.md: missing hermes-console active docs row")

    if violations:
        for violation in violations:
            print(violation)
        print(f"project-registry-ssot: FAIL ({len(violations)} violations)")
        return 1

    print("project-registry-ssot: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
