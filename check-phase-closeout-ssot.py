#!/usr/bin/env python3
from __future__ import annotations

import sys

from lib.bootstrap import workspace_root
from lib.ssot_checker import SSOTChecker

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

FORBIDDEN = ("## 当前状态",)


def main() -> int:
    checker = SSOTChecker(root=workspace_root())
    checker.check_targets_with_forbidden(TARGETS, FORBIDDEN)
    if checker.has_errors:
        checker.print_report()
        return 1
    print("PASS: historical phase closeout docs are explicitly separated from live SSOT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
