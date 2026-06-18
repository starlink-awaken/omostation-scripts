#!/usr/bin/env python3
"""检查 _truth/INVENTORY.md 是否保持为索引文档而非运行时快照。"""

from __future__ import annotations

from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
INVENTORY = WORKSPACE / ".omo" / "_truth" / "INVENTORY.md"
TRUTH_INDEX = WORKSPACE / ".omo" / "_truth" / "INDEX.md"


def main() -> int:
    violations: list[str] = []

    inventory_text = INVENTORY.read_text(encoding="utf-8")
    truth_index_text = TRUTH_INDEX.read_text(encoding="utf-8")

    required_inventory_needles = (
        "项目资产导航，不是 live runtime snapshot",
        "[../PROJECTS.yaml](../PROJECTS.yaml)",
        "[../../docs/PANORAMA.md](../../docs/PANORAMA.md)",
        "只做索引与路由，不复写运行时快照",
    )
    forbidden_inventory_needles = (
        "性质: live inventory snapshot",
        "当前 `projects/` 可见项目",
        "kairon 包数",
    )

    for needle in required_inventory_needles:
        if needle not in inventory_text:
            violations.append(f".omo/_truth/INVENTORY.md: missing `{needle}`")

    for needle in forbidden_inventory_needles:
        if needle in inventory_text:
            violations.append(f".omo/_truth/INVENTORY.md: forbidden stale snapshot text `{needle}`")

    if "_truth/INVENTORY.md" not in truth_index_text:
        violations.append(".omo/_truth/INDEX.md: missing INVENTORY.md index entry")

    if violations:
        for violation in violations:
            print(violation)
        print(f"truth-inventory-routing: FAIL ({len(violations)} violations)")
        return 1

    print("truth-inventory-routing: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
