#!/usr/bin/env python3
"""检查 governance surfaces registry 与 omo_paths 路径常量是否一致。

纯文本/AST 校验, 不依赖额外运行时依赖。
"""

from __future__ import annotations

import ast
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
OMO_PATHS = WORKSPACE / "projects/omo/src/omo/omo_paths.py"
REGISTRY = WORKSPACE / ".omo/_truth/registry/omo-governance-surfaces.yaml"

EXPECTED = {
    ".omo/_truth/": "TRUTH_DIR",
    ".omo/_control/": "CONTROL_DIR",
    ".omo/_knowledge/": "KNOWLEDGE_DIR",
    ".omo/_delivery/": "DELIVERY_DIR",
    ".omo/_archive/": "ARCHIVE_DIR",
    ".omo/tasks/": "TASKS_DIR",
    ".omo/tasks/planned/": "TASKS_PLANNED_DIR",
    ".omo/state/": "STATE_DIR",
    ".omo/debt/": "DEBT_DIR",
    ".omo/workers/": "WORKERS_DIR",
    ".omo/standards/": "STANDARDS_DIR",
    ".omo/cron/": "CRON_DIR",
    ".omo/_log/": "LOG_DIR",
    ".omo/goals/": "GOALS_DIR",
    ".omo/pitches/": "PITCHES_DIR",
    ".omo/tests/": "TESTS_DIR",
    ".omo/capabilities/": "CAPABILITIES_DIR",
    ".omo/change-log/": "CHANGE_LOG_DIR",
    ".omo/PROJECTS.yaml": "PROJECTS_REGISTRY_YAML",
    ".omo/INDEX.md": "ROOT_INDEX_MD",
    ".omo/evidence/": "EVIDENCE_ALIAS_DIR",
    ".omo/_delivery/evidence-legacy/": "EVIDENCE_LEGACY_DIR",
}


def _collect_constant_names() -> set[str]:
    tree = ast.parse(OMO_PATHS.read_text(encoding="utf-8"), filename=str(OMO_PATHS))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def main() -> int:
    constants = _collect_constant_names()
    registry_text = REGISTRY.read_text(encoding="utf-8")
    violations: list[str] = []

    for ref, constant in EXPECTED.items():
        if ref not in registry_text:
            violations.append(f"registry missing surface ref: {ref}")
        if constant not in constants:
            violations.append(f"omo_paths missing constant: {constant} for {ref}")

    # Ensure critical exported constants are in __all__ by raw text.
    omo_paths_text = OMO_PATHS.read_text(encoding="utf-8")
    for constant in EXPECTED.values():
        if f'"{constant}"' not in omo_paths_text:
            violations.append(f"omo_paths __all__ missing export: {constant}")

    if violations:
        for violation in violations:
            print(violation)
        print(f"governance-surface-paths: FAIL ({len(violations)} violations)")
        return 1

    print("governance-surface-paths: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
