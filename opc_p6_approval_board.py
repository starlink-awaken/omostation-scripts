#!/usr/bin/env python3
"""P6 self-evolution approval board.

把 `.omo/tasks/planned/OPC-P6-SELF-EVOLUTION-*.yaml` 汇总成 reviewer 可看的
当前看板，明确哪些任务在等人工批准。
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.omo_io import write_text_atomic


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_tasks() -> list[dict[str, Any]]:
    planned_dir = ROOT / ".omo" / "tasks" / "planned"
    entries: list[dict[str, Any]] = []
    for path in sorted(planned_dir.glob("OPC-P6-SELF-EVOLUTION-*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries.append(
            {
                "task_id": payload.get("id", path.stem),
                "task_ref": str(path.relative_to(ROOT)),
                "status": payload.get("status", "planned"),
                "approval_required": bool(
                    payload.get("approval_required", payload.get("human_approval_required", False))
                ),
                "approval_state": payload.get("approval_state", "awaiting_human"),
                "latest_week": payload.get("latest_week"),
                "loop_history_ref": payload.get("loop_history_ref"),
                "created_at": payload.get("created_at"),
                "title": payload.get("title"),
            }
        )
    return entries


def build_board() -> dict[str, Any]:
    tasks = _load_tasks()
    # SSOT 修正: latest_week 应从 .omo/_control/evolution/loop/history.json 读取
    # (而非仅从 self-evolve task 的 latest_week 字段取, 因为 approval board 需与
    # loop history 对齐, 否则 approval board 落后于 loop 索引)
    loop_history_path = ROOT / ".omo" / "_control" / "evolution" / "loop" / "history.json"
    latest_week_from_loop: str | None = None
    if loop_history_path.exists():
        try:
            import yaml as _yaml
            payload = _yaml.safe_load(loop_history_path.read_text(encoding="utf-8")) or {}
            latest_week_from_loop = (
                payload.get("summary", {}).get("latest_week")
                if isinstance(payload, dict)
                else None
            )
        except Exception:
            latest_week_from_loop = None

    # 优先 loop history; 缺失时回退到 self-evolve task 自带字段
    latest_week_task = next(
        (item["latest_week"] for item in reversed(tasks) if item.get("latest_week")),
        None,
    )
    return {
        "generated_at": _now_iso(),
        "tasks": tasks,
        "summary": {
            "task_count": len(tasks),
            "awaiting_human_count": sum(1 for item in tasks if item["approval_state"] == "awaiting_human"),
            "approval_required_count": sum(1 for item in tasks if item["approval_required"]),
            "latest_week": latest_week_from_loop or latest_week_task,
            "latest_week_source": "loop_history" if latest_week_from_loop else ("self_evolve_task" if latest_week_task else None),
            "loop_history_ref": str(loop_history_path.relative_to(ROOT)),
        },
    }


def write_board(board: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = ROOT / ".omo" / "_control" / "evolution" / "approval-board"
    json_path = out_dir / "current.json"
    md_path = out_dir / "current.md"
    write_text_atomic(json_path, json.dumps(board, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# OPC P6 approval board",
        "",
        f"Generated: {board['generated_at']}",
        "",
        f"- task_count: {board['summary']['task_count']}",
        f"- awaiting_human_count: {board['summary']['awaiting_human_count']}",
        f"- approval_required_count: {board['summary']['approval_required_count']}",
        f"- latest_week: {board['summary']['latest_week']}",
        f"- latest_week_source: {board['summary'].get('latest_week_source', 'self_evolve_task')}",
        "",
        "| Task | Status | Approval | Latest Week | Ref |",
        "|------|--------|----------|-------------|-----|",
    ]
    for item in board["tasks"]:
        lines.append(
            f"| {item['task_id']} | {item['status']} | {item['approval_state']} | {item.get('latest_week') or '-'} | `{item['task_ref']}` |"
        )
    write_text_atomic(md_path, "\n".join(lines) + "\n")
    return json_path, md_path


def main() -> int:
    board = build_board()
    json_path, md_path = write_board(board)
    print(f"# json: {json_path.relative_to(ROOT)}")
    print(f"# md: {md_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
