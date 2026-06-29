#!/usr/bin/env python3
from __future__ import annotations

import sys

from lib.bootstrap import workspace_root


ROOT = workspace_root()
README = ROOT / ".omo/_knowledge/design/plans/README.md"


def section(text: str, title: str, next_title: str | None = None) -> str:
    start = text.index(title)
    end = text.index(next_title, start) if next_title else len(text)
    return text[start:end]


def require(text: str, needle: str, label: str, errors: list[str]) -> None:
    if needle not in text:
        errors.append(f"{label}: missing `{needle}`")


def forbid(text: str, needle: str, label: str, errors: list[str]) -> None:
    if needle in text:
        errors.append(f"{label}: forbidden `{needle}`")


def main() -> int:
    text = README.read_text(encoding="utf-8")
    errors: list[str] = []

    active = section(text, "## 🟡 ACTIVE", "## 🟢 REFERENCE")
    reference = section(text, "## 🟢 REFERENCE", "## ⚪ ARCHIVED")
    preplanning = section(text, "## 🔵 PRE-PLANNING", "## 🟡 ACTIVE")

    require(active, "evolution-roadmap-4phases.md", "ACTIVE", errors)
    require(active, "planning-blueprint-delivery-test-standard.md", "ACTIVE", errors)
    require(active, "phase2-phase3-task-manifest.md", "ACTIVE", errors)

    for needle in [
        "phase5-program-plan.md",
        "phase6-program-plan.md",
        "phase7-program-plan.md",
        "phase8-program-plan.md",
        "phase9-program-plan.md",
        "phase10-program-plan.md",
        "phase11-program-plan.md",
        "phase12-program-plan.md",
        "phase14-program-plan.md",
        "phase15-autonomous-governance-preplanning.md",
        "phase16-product-surface-convergence-preplanning.md",
    ]:
        forbid(active, needle, "ACTIVE", errors)

    require(preplanning, "phase17-wave1-sharedbrain-decomposition-plan.md", "PRE-PLANNING", errors)
    forbid(preplanning, "phase15-autonomous-governance-preplanning.md", "PRE-PLANNING", errors)
    forbid(preplanning, "phase16-product-surface-convergence-preplanning.md", "PRE-PLANNING", errors)

    for needle in [
        "phase5-program-plan.md",
        "phase6-program-plan.md",
        "phase7-program-plan.md",
        "phase11-program-plan.md",
        "phase12-program-plan.md",
        "phase14-program-plan.md",
        "phase15-autonomous-governance-preplanning.md",
        "phase16-product-surface-convergence-preplanning.md",
    ]:
        require(reference, needle, "REFERENCE", errors)

    if errors:
        print("FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("PASS: plans/README status buckets separate active planning from historical packets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
