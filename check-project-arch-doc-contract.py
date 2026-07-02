#!/usr/bin/env python3
"""检查项目级 ARCHITECTURE/CALLCHAIN/BOUNDARY 文档契约。

目标:
1. 各项目三件套文档都存在
2. ARCHITECTURE.md 必须回指 workspace panorama/architecture diagram
3. CALLCHAIN.md 必须回指通用跨层调用链
4. BOUNDARY.md 必须回指架构演进对比，并显式给出 `配置 / SSOT` 段
"""

from __future__ import annotations

from pathlib import Path

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


def _check_contains(path: Path, required: tuple[str, ...], violations: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for needle in required:
        if needle not in text:
            violations.append(f"{path.relative_to(WORKSPACE)}: missing `{needle}`")


def main() -> int:
    violations: list[str] = []

    for project in PROJECTS:
        base = WORKSPACE / "projects" / project
        architecture = base / "ARCHITECTURE.md"
        callchain = base / "CALLCHAIN.md"
        boundary = base / "BOUNDARY.md"

        for path in (architecture, callchain, boundary):
            if not path.exists():
                violations.append(f"missing doc: {path.relative_to(WORKSPACE)}")
                continue

        if architecture.exists():
            _check_contains(
                architecture,
                (
                    "#",
                    "## 1. 内部架构",
                    "## 2. 入口",
                    "## 3. 核心模块",
                    "## 4. 测试",
                    "docs/ARCHITECTURE-DIAGRAM.md",
                ),
                violations,
            )

        if callchain.exists():
            _check_contains(
                callchain,
                (
                    "#",
                    "## 关键路径",
                    "## Sequence Diagram",
                    "docs/I0-AGORA-CALLCHAIN.md",
                ),
                violations,
            )

        if boundary.exists():
            _check_contains(
                boundary,
                (
                    "#",
                    "## 1. 暴露接口",
                    "## 2. 上游依赖",
                    "## 3. 下游影响",
                    "## 4. 配置 / SSOT",
                    "docs/ARCHITECTURE-EVOLUTION.md",
                ),
                violations,
            )

    if violations:
        for violation in violations:
            print(violation)
        print(f"project-arch-doc-contract: FAIL ({len(violations)} violations)")
        return 1

    print("project-arch-doc-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
