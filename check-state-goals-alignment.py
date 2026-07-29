#!/usr/bin/env python3
"""
检查 .omo/state/system.yaml 和 .omo/goals/current.yaml 之间的对齐。
检测 divergence_flags 并输出告警。

用法：
    python3 scripts/check-state-goals-alignment.py
    返回值：0 = 对齐，1 = 不一致
"""

from __future__ import annotations

from lib.paths import GOALS_YAML, OMO_DIR, SYSTEM_YAML
from lib.yaml_utils import load_yaml, load_yaml_multi


def _load_task(path):
    """Read the first mapping from a task file, including multi-document YAML."""
    for document in load_yaml_multi(path):
        if isinstance(document, dict):
            return document
    return {}


def _current_phase(goals_data: dict) -> int | None:
    phase = goals_data.get("phase")
    return phase if isinstance(phase, int) else None


def _current_goal_task_ids(goals_data: dict) -> set[str]:
    active_phase = _current_phase(goals_data)
    goal_task_ids: set[str] = set()
    for goal in goals_data.get("goals", []):
        if goal.get("status") == "gated":
            continue
        goal_id = str(goal.get("id", ""))
        if active_phase is not None and goal_id.startswith("G") and "." in goal_id:
            phase_prefix = goal_id[1:].split(".", 1)[0]
            if phase_prefix.isdigit() and int(phase_prefix) != active_phase:
                continue
        goal_task_ids.update(goal.get("tasks", []))
    return goal_task_ids


def main() -> int:
    omo_dir = OMO_DIR
    state_path = SYSTEM_YAML
    goals_path = GOALS_YAML

    if not state_path.exists():
        print(f"ERROR: {state_path} not found")
        return 1
    if not goals_path.exists():
        print(f"ERROR: {goals_path} not found")
        return 1

    state = load_yaml(state_path)
    goals_docs = load_yaml_multi(goals_path)
    goals = {}
    for doc in goals_docs:
        if isinstance(doc, dict):
            goals.update(doc)

    active_phase = _current_phase(goals)
    goal_task_ids = _current_goal_task_ids(goals)

    task_ids: set[str] = set()
    done_ids: set[str] = set()  # done 历史 task 不算 orphaned (已完成的可在 current goals 之外)
    for group in ("active", "blocked", "done"):
        for task_file in (omo_dir / "tasks" / group).rglob("*.yaml"):
            task = _load_task(task_file)
            task_id = task.get("id")
            if not task_id:
                continue
            task_phase = task.get("phase")
            if active_phase is not None and task_phase not in {None, active_phase}:
                continue
            if task_phase is None and task_id not in goal_task_ids:
                continue
            task_ids.add(task_id)
            if group == "done":
                done_ids.add(task_id)
    # archived tasks (历史归档) 也算 done — 不算 orphaned / missing
    for archive_dir in ("archived", "archive"):
        archive_root = omo_dir / "tasks" / archive_dir
        if not archive_root.exists():
            continue
        for task_file in archive_root.rglob("*.yaml"):
            task = _load_task(task_file)
            task_id = task.get("id")
            if not task_id:
                continue
            task_status = task.get("status")
            if task_status in ("done", "completed", "archived"):
                done_ids.add(task_id)
                task_ids.add(task_id)

    missing = sorted(goal_task_ids - task_ids)
    orphaned = sorted((task_ids - done_ids) - goal_task_ids)
    flags = []
    if missing:
        flags.append(f"missing_goal_tasks:{','.join(missing)}")
    if orphaned:
        flags.append(f"orphaned_tasks:{','.join(orphaned)}")

    divergence = state.get("divergence_flags", [])

    # computed (flags) 是真源 — 从 goals/tasks 实时算. state (divergence) 是 snapshot,
    # 由 governance loop 维护, 可能漂移. 真源对齐 (flags 空) 时, state stale 只 warning,
    # 不阻断 CI (governance loop 该刷新 state, 非 CI 阻断事由).
    real_aligned = not flags

    if real_aligned:
        if divergence:
            print(
                f"::warning::State divergence_flags stale: state={list(divergence)} "
                f"but computed empty (goals/tasks realigned). Governance loop should refresh state."
            )
            return 0
        print("State-goals alignment: OK")
        return 0

    # 真源有 missing/orphaned — 真 divergence, 阻断.
    if divergence != flags:
        print("::warning::State divergence flags mismatch")
        print(f"  Expected: {flags}")
        print(f"  Found:    {divergence}")
        return 1

    for flag in flags:
        print(f"::warning::Divergence flag: {flag}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
