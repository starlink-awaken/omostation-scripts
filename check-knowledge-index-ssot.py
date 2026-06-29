#!/usr/bin/env python3
"""检查知识面入口索引是否保持为导航，而不是运行时快照。"""

from __future__ import annotations


from lib.bootstrap import workspace_root

WORKSPACE = workspace_root()

TARGETS = {
    ".omo/_knowledge/design/plans/README.md": (
        "不是运行时状态快照",
        "/.omo/goals/current.yaml",
        "/.omo/state/system.yaml",
        "/.omo/tasks/active/",
    ),
    ".omo/_knowledge/design/INDEX.md": (
        "不是阶段状态快照",
        "plans/README.md",
        "/.omo/goals/current.yaml",
        "/.omo/tasks/active/",
    ),
    ".omo/_knowledge/management/INDEX.md": (
        "只做管理文档导航",
        "control/truth SSOT",
    ),
    ".omo/_knowledge/design/plans/layer-capability-user-planning.md": (
        "历史分析输入，不是当前项目拓扑或运行时事实源",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
}

FORBIDDEN = {
    ".omo/_knowledge/design/plans/README.md": (
        "状态: Phase",
        "Phase 16 completed",
    ),
    ".omo/_knowledge/management/INDEX.md": (
        "本地文件数:",
        "编目引用数:",
    ),
}


def main() -> int:
    violations: list[str] = []
    for rel, needles in TARGETS.items():
        text = (WORKSPACE / rel).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                violations.append(f"{rel}: missing `{needle}`")
        for needle in FORBIDDEN.get(rel, ()):
            if needle in text:
                violations.append(f"{rel}: forbidden stale snapshot text `{needle}`")

    if violations:
        for violation in violations:
            print(violation)
        print(f"knowledge-index-ssot: FAIL ({len(violations)} violations)")
        return 1

    print("knowledge-index-ssot: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
