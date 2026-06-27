#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

from lib.bootstrap import workspace_root


ROOT = workspace_root()

TARGETS = {
    ".omo/_knowledge/summaries/phase17/phase17-closeout.md": (
        "Historical closeout record / reference only.",
        "is not the current phase/system/debt SSOT",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
        "/.omo/debt/",
        "## 历史收口状态快照",
    ),
    ".omo/_knowledge/summaries/phase18/phase18-closeout.md": (
        "Historical closeout record / reference only.",
        "is not the current phase/system/debt SSOT",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
        "/.omo/debt/",
        "## 历史收口状态快照",
    ),
}

FORBIDDEN = (
    "## 当前状态",
)


def main() -> int:
    errors: list[str] = []
    for rel, needles in TARGETS.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"{rel}: missing `{needle}`")
        for needle in FORBIDDEN:
            if needle in text:
                errors.append(f"{rel}: forbidden `{needle}`")

    if errors:
        print("FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("PASS: historical phase closeout docs are explicitly separated from live SSOT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
