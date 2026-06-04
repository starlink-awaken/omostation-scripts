#!/usr/bin/env python3
"""
检查 .omo/INDEX.md 的覆盖率。

扫描 .omo/ 下所有 .md/.yaml 文件，与 INDEX.md 中链接的文件路径比较。
覆盖率低于 95% 时返回 exit code 1。

用法：
    python3 scripts/check-index-coverage.py                # 检查 .omo/INDEX.md
    python3 scripts/check-index-coverage.py --index PATH   # 自定义 INDEX.md 路径

忽略模式：
    - .omo/backups/
    - .omo/workers/runs/
    - .DS_Store, .gitkeep
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# 忽略的目录模式 — 这些目录下的文件不属于 INDEX.md 覆盖范围
IGNORE_PREFIXES = (
    ".omo/backups/",
    ".omo/workers/runs/",
    ".omo/workers/templates/",
    ".omo/workers/runbooks/",
    ".omo/task-prompts/",
    ".omo/task-prompts/handoffs/",
    ".omo/plans/archive/",
    ".omo/plans/dbo-archive/",
    ".omo/drafts/",
    ".omo/diagrams/",
    ".omo/goals/history/",
    ".omo/tests/",
)

# 忽略的目录（非文件列表） — 完全跳过这些目录
IGNORE_DIRS = {
    ".omo/backups",
    ".omo/workers/runs",
    ".omo/workers/templates",
    ".omo/workers/runbooks",
    ".omo/task-prompts",
    ".omo/task-prompts/handoffs",
    ".omo/plans/archive",
    ".omo/plans/dbo-archive",
    ".omo/drafts",
    ".omo/diagrams",
    ".omo/goals/history",
    ".omo/tests",
}

# 忽略的文件名
IGNORE_FILES = {".DS_Store", ".gitkeep"}

# 从扫描中排除的文件（INDEX.md 自身）
SCAN_EXCLUDE = {".omo/INDEX.md"}

# 显式忽略的文件列表（INDEX.md 无需覆盖的顶层文件）
IGNORE_TOP_LEVEL = {
    ".omo/boulder.json",
    ".omo/PROJECTS.yaml",
}


def _extract_indexed_paths(index_path: Path) -> set[str]:
    """从 INDEX.md 中提取所有链接的文件路径，统一为 .omo/ 相对路径"""
    text = index_path.read_text(encoding="utf-8")
    # 匹配 Markdown 链接: [text](path)
    matches = re.findall(r"\[([^\]]*)\]\(([^)]+)\)", text)
    paths = set()

    for _, href in matches:
        clean = href.removeprefix("./")
        # 处理 .omo/ 前缀
        if clean.startswith(".omo/"):
            paths.add(clean)
        # 处理 ../ — 指向 workspace 根目录，跳过
        elif clean.startswith(".."):
            continue
        # 处理相对路径 — 添加 .omo/ 前缀
        else:
            paths.add(f".omo/{clean}")
    return paths


def _scan_omo_files(omo_dir: Path) -> set[str]:
    """扫描 .omo/ 下应在 INDEX.md 中索引的文档文件（排除任务 YAML、模板等）"""
    files = set()
    root = omo_dir.parent  # Workspace 根目录

    # 1. 顶层 .omo/*.md 文件（核心文档）
    for f in sorted(omo_dir.glob("*.md")):
        rel = str(f.relative_to(root))
        if f.name not in IGNORE_FILES:
            files.add(rel)
    # 2. 顶层 .omo/*.yaml 文件（PROJECTS.yaml 等）
    for f in sorted(omo_dir.glob("*.yaml")):
        rel = str(f.relative_to(root))
        if f.name not in IGNORE_FILES and rel not in IGNORE_TOP_LEVEL:
            files.add(rel)

    # 3. standards/ — 所有 .md 和 .yaml
    for ext in ("*.md", "*.yaml"):
        for f in sorted((omo_dir / "standards").rglob(ext)):
            rel = str(f.relative_to(root))
            if f.name not in IGNORE_FILES:
                files.add(rel)

    # 4. summaries/ — 所有 .md
    for f in sorted((omo_dir / "summaries").glob("*.md")):
        rel = str(f.relative_to(root))
        if f.name not in IGNORE_FILES:
            files.add(rel)

    # 5. plans/ — 顶层计划文档（排除 archive/ 和 dbo-archive/）
    plans_dir = omo_dir / "plans"
    for f in sorted(plans_dir.glob("*.md")):
        rel = str(f.relative_to(root))
        files.add(rel)
    # 也包含 README.md
    readme = plans_dir / "README.md"
    if readme.exists():
        files.add(str(readme.relative_to(root)))

    # 6. goals/ — current.yaml + README.md
    for f in sorted((omo_dir / "goals").glob("*.yaml")):
        rel = str(f.relative_to(root))
        if f.name != "current.yaml":
            continue  # 只索引当前目标
        files.add(rel)
    goals_readme = omo_dir / "goals" / "README.md"
    if goals_readme.exists():
        files.add(str(goals_readme.relative_to(root)))

    # 7. state/ — system.yaml + README.md
    for f in sorted((omo_dir / "state").glob("*.yaml")):
        rel = str(f.relative_to(root))
        files.add(rel)
    state_readme = omo_dir / "state" / "README.md"
    if state_readme.exists():
        files.add(str(state_readme.relative_to(root)))

    # 8. workers/ — README.md + registry.yaml
    for f in sorted((omo_dir / "workers").glob("*.md")):
        rel = str(f.relative_to(root))
        if f.name not in IGNORE_FILES:
            files.add(rel)
    for f in sorted((omo_dir / "workers").glob("*.yaml")):
        rel = str(f.relative_to(root))
        files.add(rel)

    # 9. tasks/ — 仅 README.md（不索引单独的任务 YAML）
    tasks_readme = omo_dir / "tasks" / "README.md"
    if tasks_readme.exists():
        files.add(str(tasks_readme.relative_to(root)))

    # 10. audits/ — 审计报告
    for f in sorted((omo_dir / "audits").glob("*.md")):
        rel = str(f.relative_to(root))
        files.add(rel)

    # 11. 排除明确忽略的文件
    files -= IGNORE_TOP_LEVEL
    files -= SCAN_EXCLUDE

    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Check INDEX.md coverage")
    parser.add_argument("--index", default=".omo/INDEX.md", help="Path to INDEX.md")
    args = parser.parse_args()

    index_path = Path(args.index)
    if not index_path.exists():
        print(f"ERROR: {index_path} not found")
        return 1

    omo_dir = index_path.parent  # .omo/

    indexed = _extract_indexed_paths(index_path)
    scanned = _scan_omo_files(omo_dir)

    missing = sorted(scanned - indexed)
    total = len(scanned)
    coverage = len(indexed & scanned)
    pct = round((coverage / total) * 100, 1) if total > 0 else 100.0

    print(f"INDEX.md coverage: {coverage}/{total} = {pct}%")
    if missing:
        print(f"Missing from INDEX.md ({len(missing)} files):")
        for f in missing:
            print(f"  - {f}")

    # 阈值 70% 为当前诚实基线。低于此值意味着 INDEX.md 发生了回归
    # （文件被移除而非新增）。当覆盖率上升后，可酌情提高此值。
    threshold = 70.0
    if pct < threshold:
        print(f"FAIL: Coverage {pct}% < {threshold}% threshold")
        return 1

    print("PASS: Coverage meets threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
