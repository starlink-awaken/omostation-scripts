#!/usr/bin/env python3
"""
检查 .omo/state/system.yaml 和 .omo/goals/current.yaml 之间的对齐。
检测 divergence_flags 并输出告警。

用法：
    python3 scripts/check-state-goals-alignment.py
    返回值：0 = 对齐，1 = 不一致
"""

from __future__ import annotations

from pathlib import Path

import yaml


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
    omo_dir = Path(".omo")
    state_path = omo_dir / "state" / "system.yaml"
    goals_path = omo_dir / "goals" / "current.yaml"

    if not state_path.exists():
        print(f"ERROR: {state_path} not found")
        return 1
    if not goals_path.exists():
        print(f"ERROR: {goals_path} not found")
        return 1

    state = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
    goals = yaml.safe_load(goals_path.read_text(encoding="utf-8")) or {}

    active_phase = _current_phase(goals)
    goal_task_ids = _current_goal_task_ids(goals)

    task_ids: set[str] = set()
    for group in ("active", "blocked", "done"):
        for task_file in (omo_dir / "tasks" / group).rglob("*.yaml"):
            task = yaml.safe_load(task_file.read_text(encoding="utf-8")) or {}
            task_id = task.get("id")
            if not task_id:
                continue
            task_phase = task.get("phase")
            if active_phase is not None and task_phase not in {None, active_phase}:
                continue
            if task_phase is None and task_id not in goal_task_ids:
                continue
            task_ids.add(task_id)

    missing = sorted(goal_task_ids - task_ids)
    orphaned = sorted(task_ids - goal_task_ids)
    flags = []
    if missing:
        flags.append(f"missing_goal_tasks:{','.join(missing)}")
    if orphaned:
        flags.append(f"orphaned_tasks:{','.join(orphaned)}")

    divergence = state.get("divergence_flags", [])
    computed = set(divergence)
    expected = set(flags)

    all_ok = not flags and not (computed - expected)

    if all_ok:
        if divergence:
            # state 中有 divergence flag 但实际已修复 — 说明 state 过期
            print("::warning::State divergence flags present but all tasks are aligned (stale flags)")
            return 1
        print("State-goals alignment: OK")
        return 0

    if divergence != flags:
        print("::warning::State divergence flags mismatch")
        print(f"  Expected: {flags}")
        print(f"  Found:    {divergence}")
        return 1

    for flag in divergence:
        print(f"::warning::Divergence flag: {flag}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
