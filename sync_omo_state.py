#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from lib.bootstrap import workspace_root, omo_src_path
from lib.paths import OMO_DIR

WORKSPACE_ROOT = workspace_root()
OMO_SRC = omo_src_path()
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))

from omo.omo_debt_weight import compute_debt_weight, debt_summary
from omo.omo_debt_metrics import compute_debt_metrics
from omo.omo_debt_registry import load_debt_ledger
from omo.omo_io import write_yaml_atomic
from omo.omo_state_schema import (
    summarize_system_health_snapshot,
    validate_system_state,
)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    docs = [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]
    if not docs:
        return {}
    if len(docs) == 1:
        return docs[0] if isinstance(docs[0], dict) else {}

    merged: dict = {}
    for doc in docs:
        if isinstance(doc, dict):
            merged.update(doc)
    return merged


def _write_yaml(path: Path, data: dict) -> None:
    write_yaml_atomic(path, data)


def _omo_ref(omo_dir: Path) -> Path:
    return Path(omo_dir.name)


def _resolve_evidence_write_path(omo_dir: Path, relative_path: Path) -> Path:
    evidence_root = omo_dir / "evidence"
    if omo_dir.name == ".omo" and evidence_root.is_symlink():
        target = evidence_root.readlink()
        if not target.is_absolute():
            target = (evidence_root.parent / target).resolve()
        return target / relative_path
    return evidence_root / relative_path


def _count_task_group(tasks_dir: Path, group: str) -> int:
    return len(list((tasks_dir / group).glob("*.yaml")))


def _parse_health_score(output: str | None, fallback: float) -> float:
    if not output:
        return fallback

    passed_match = re.search(r"(\d+)\s+passed", output, re.IGNORECASE)
    failed_match = re.search(r"(\d+)\s+failed", output, re.IGNORECASE)
    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    total = passed + failed
    if total == 0:
        return fallback
    return round((passed / total) * 100, 2)


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _write_divergence_detail_artifact(omo_dir: Path, name: str, payload: dict[str, object]) -> str:
    ref = _omo_ref(omo_dir) / "evidence" / "divergence" / f"{name}.yaml"
    _write_yaml(_resolve_evidence_write_path(omo_dir, Path("divergence") / f"{name}.yaml"), {"rule": name, **payload})
    return str(ref)


def _clear_divergence_detail_artifact(omo_dir: Path, name: str) -> None:
    candidates = [
        omo_dir / "evidence" / "divergence" / f"{name}.yaml",
        _resolve_evidence_write_path(omo_dir, Path("divergence") / f"{name}.yaml"),
    ]
    for path in candidates:
        if path.exists():
            path.unlink()


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


def _goal_divergence_flags(
    omo_dir: Path,
    goals_data: dict,
    task_ids: set[str],
    done_task_ids: set[str] | None = None,
) -> tuple[list[str], dict[str, dict[str, object]]]:
    """Compute goal/task divergence flags.

    P42 SSOT 同步纪元: 与 scripts/check-state-goals-alignment.py 对齐。
    - 用 rglob 递归扫描 tasks/{active,blocked,done} 及其子目录
    - done 任务不算 orphaned (历史归档不影响当前对齐)
    """
    goal_task_ids = _current_goal_task_ids(goals_data)
    done_task_ids = done_task_ids or set()

    flags: list[str] = []
    detail_refs: dict[str, dict[str, object]] = {}
    missing = sorted(goal_task_ids - task_ids)
    if missing:
        flags.append(f"missing_goal_tasks:{len(missing)}")
        detail_refs["missing_goal_tasks"] = {
            "count": len(missing),
            "ref": _write_divergence_detail_artifact(
                omo_dir,
                "missing_goal_tasks",
                {"count": len(missing), "task_ids": missing},
            ),
        }
    # Done tasks 是历史归档, 不算 orphaned
    orphaned = sorted((task_ids - done_task_ids) - goal_task_ids)
    if orphaned:
        flags.append(f"orphaned_tasks:{len(orphaned)}")
        detail_refs["orphaned_tasks"] = {
            "count": len(orphaned),
            "ref": _write_divergence_detail_artifact(
                omo_dir,
                "orphaned_tasks",
                {"count": len(orphaned), "task_ids": orphaned},
            ),
        }
    return flags, detail_refs


def _active_task_ref_flags(active_dir: Path) -> list[str]:
    flags: list[str] = []
    for task_file in sorted(active_dir.glob("*.yaml")):
        task = _load_yaml(task_file)
        task_id = task.get("id", task_file.stem)
        status = task.get("status")
        requires_run_chain = status in {"in_progress", "review", "done"}
        if requires_run_chain and not task.get("run_ref"):
            flags.append(f"active_task_missing_run_ref:{task_id}")
        if requires_run_chain and not task.get("review_ref"):
            flags.append(f"active_task_missing_review_ref:{task_id}")
    return flags


def _dispatch_for_task(omo_dir: Path, task: dict) -> dict | None:
    run_ref = task.get("run_ref")
    if not run_ref:
        return None
    dispatch_path = omo_dir.parent / run_ref
    if not dispatch_path.exists():
        return None
    return _load_yaml(dispatch_path)


def _stale_dispatch_flags(omo_dir: Path, now: datetime) -> tuple[list[str], dict[str, dict[str, object]]]:
    flags: list[str] = []
    task_ids: list[str] = []
    for task_file in sorted((omo_dir / "tasks" / "active").glob("*.yaml")):
        task = _load_yaml(task_file)
        dispatch = _dispatch_for_task(omo_dir, task)
        if not dispatch:
            continue
        lease = dispatch.get("lease", {})
        last_seen = _parse_iso8601(lease.get("last_material_write_at")) or _parse_iso8601(dispatch.get("launched_at"))
        expiry = lease.get("lease_expired_after_seconds")
        if last_seen and expiry and (now - last_seen).total_seconds() > expiry:
            task_id = task.get("id", task_file.stem)
            flags.append(f"stale_dispatch:{task_id}")
            task_ids.append(task_id)

    detail_refs: dict[str, dict[str, object]] = {}
    if task_ids:
        detail_refs["stale_dispatches"] = {
            "count": len(task_ids),
            "ref": _write_divergence_detail_artifact(
                omo_dir,
                "stale_dispatches",
                {"count": len(task_ids), "task_ids": sorted(task_ids)},
            ),
        }
    return flags, detail_refs


def _dangling_reference_flags(omo_dir: Path) -> tuple[list[str], dict[str, dict[str, object]]]:
    flags: list[str] = []
    task_to_missing: dict[str, list[str]] = {}
    for task_file in sorted((omo_dir / "tasks" / "active").glob("*.yaml")):
        task = _load_yaml(task_file)
        task_id = task.get("id", task_file.stem)
        refs = [
            task.get("run_ref"),
            task.get("review_ref"),
            *task.get("knowledge_refs", []),
            *task.get("handoff_refs", []),
        ]
        missing = [ref for ref in refs if ref and not (omo_dir.parent / ref).exists()]
        if missing:
            flags.append(f"dangling_refs:{task_id}")
            task_to_missing[task_id] = sorted(set(missing))

    detail_refs: dict[str, dict[str, object]] = {}
    if task_to_missing:
        detail_refs["dangling_refs"] = {
            "count": len(task_to_missing),
            "ref": _write_divergence_detail_artifact(
                omo_dir,
                "dangling_refs",
                {
                    "count": len(task_to_missing),
                    "task_ids": sorted(task_to_missing),
                    "missing_refs": [ref for refs in task_to_missing.values() for ref in refs],
                },
            ),
        }
    return flags, detail_refs


def _debt_generated_ref_flags(omo_dir: Path, ledger) -> tuple[list[str], dict[str, dict[str, object]]]:
    refs = {
        "dashboard_ref": ledger.dashboard_ref,
        "review_pack_ref": ledger.review_pack_ref,
        "review_queue_ref": ledger.review_queue_ref,
        "action_packet_ref": ledger.action_packet_ref,
        "owner_routing_ref": ledger.owner_routing_ref,
        "dispatch_ref": ledger.dispatch_ref,
        "campaign_ref": ledger.campaign_ref,
        "reporting_ref": ledger.reporting_ref,
    }
    missing = {name: ref for name, ref in refs.items() if not (omo_dir.parent / ref).exists()}
    if not missing:
        return [], {}
    return (
        [f"missing_debt_generated_ref:{name}" for name in sorted(missing)],
        {
            "debt_generated_refs": {
                "count": len(missing),
                "ref": _write_divergence_detail_artifact(
                    omo_dir,
                    "debt_generated_refs",
                    {"count": len(missing), "missing_refs": missing},
                ),
            }
        },
    )


def _derive_gate_facts(task: dict, dispatch: dict | None) -> list[str]:
    facts: list[str] = []
    if task.get("dispatch_id") and task.get("run_ref") and task.get("assigned_to"):
        facts.append("dispatched")
    reclaim = dispatch.get("reclaim", {}) if dispatch else {}
    if (
        reclaim.get("note_ref")
        and reclaim.get("successor_dispatch_id")
        and reclaim.get("successor_worker_id")
    ):
        facts.append("reclaimed")
    if task.get("review_ref"):
        facts.append("review_ready")
    return facts


def _task_has_blocking_divergence(task_id: str, divergence_flags: list[str]) -> bool:
    for flag in divergence_flags:
        _, _, suffix = flag.partition(":")
        if not suffix:
            continue
        task_ids = suffix.split(",")
        if task_id in task_ids:
            return True
    return False


def _promotion_blockers(task_id: str, task: dict, gate_facts: list[str], divergence_flags: list[str]) -> list[str]:
    blockers: list[str] = []
    status = task.get("status")
    if status in {"in_progress", "review", "done"} and not task.get("dispatch_id"):
        blockers.append("missing_dispatch_id")
    if status in {"in_progress", "review", "done"} and not task.get("run_ref"):
        blockers.append("missing_run_ref")
    if status in {"in_progress", "review", "done"} and "dispatched" in gate_facts and not task.get("review_ref"):
        blockers.append("missing_review_ref")
    if status in {"review", "done"} and task.get("evidence_required") and "review_ready" not in gate_facts:
        blockers.append("evidence_not_ready")
    if status == "done" and not task.get("completion_summary"):
        blockers.append("missing_completion_summary")
    if status == "done" and _task_has_blocking_divergence(task_id, divergence_flags):
        blockers.append("blocking_divergence")
    return blockers


def _task_gate_summary(omo_dir: Path, divergence_flags: list[str]) -> tuple[dict[str, dict[str, object]], dict[str, list[str]]]:
    summary: dict[str, dict[str, object]] = {}
    blockers: dict[str, list[str]] = {}
    active_dir = omo_dir / "tasks" / "active"
    for task_file in sorted(active_dir.glob("*.yaml")):
        task = _load_yaml(task_file)
        task_id = task.get("id", task_file.stem)
        gate_facts = _derive_gate_facts(task, _dispatch_for_task(omo_dir, task))
        task_blockers = _promotion_blockers(task_id, task, gate_facts, divergence_flags)
        if task.get("status") == "done" and not task_blockers:
            gate_facts.append("accepted")
        summary[task_id] = {
            "canonical_status": task.get("status"),
            "gate_facts": gate_facts,
        }
        blockers[task_id] = task_blockers
    return summary, blockers


def _load_triage_rules(omo_dir: Path) -> dict[str, dict[str, str]]:
    triage_path = omo_dir / "standards" / "divergence-triage.yaml"
    if not triage_path.exists():
        return {}
    return _load_yaml(triage_path).get("rules", {})


def _match_triage_rule(flag: str, rules: dict[str, dict[str, str]]) -> dict[str, str]:
    prefix = flag.split(":", 1)[0]
    return rules.get(prefix, {"severity": "low", "owner": "control", "disposition": "monitor"})


def _divergence_triage_summary(flags: list[str], rules: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    return {flag: _match_triage_rule(flag, rules) for flag in flags}


def _looks_like_task_queue_entry(line: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9._-]*", line))


def _queue_preview(group_dir: Path, state_lines: list[str] | None, omo_ref: Path, label: str) -> list[str]:
    """从任务目录读取队列列表，保留 state 中的额外描述"""
    task_ids = []
    for task_file in sorted(group_dir.glob("*.yaml")):
        task = _load_yaml(task_file)
        task_ids.append(task.get("id", task_file.stem))

    if not task_ids:
        return [f"(No {label} tasks)"]

    suffix = "task" if len(task_ids) == 1 else "tasks"
    queue_name = group_dir.name
    header = f"Current {label} queue from {omo_ref}/tasks/{queue_name}/ ({len(task_ids)} {suffix})"
    header_prefix = f"Current {label} queue from {omo_ref}/tasks/{queue_name}/ ("
    extras = [
        line
        for line in (state_lines or [])
        if not line.startswith(header_prefix)
        and line not in task_ids
        and line != f"(No {label} tasks)"
        and not _looks_like_task_queue_entry(line)
    ]

    return [header, *task_ids, *extras]


def sync_state(
    omo_dir: Path,
    test_output: str | None = None,
    now: str | None = None,
    xplane_factor: float | None = 1.0,  # 1.0 = 无折扣(测试隔离); None 触发实时探活
) -> dict:
    state_path = omo_dir / "state" / "system.yaml"
    health_snapshot_path = omo_dir / "state" / "system_health.yaml"
    tasks_dir = omo_dir / "tasks"
    goals_path = omo_dir / "goals" / "current.yaml"

    state = _load_yaml(state_path)
    health_snapshot = _load_yaml(health_snapshot_path)
    goals = _load_yaml(goals_path)
    current_time = _parse_iso8601(now) or datetime.now(timezone.utc)
    goal_phase = goals.get("phase")
    goal_wave = goals.get("current_wave")
    goal_status = goals.get("status")
    goal_next_milestone = goals.get("next_milestone")

    active_count = _count_task_group(tasks_dir, "active")
    planned_count = _count_task_group(tasks_dir, "planned")
    blocked_count = _count_task_group(tasks_dir, "blocked")
    done_count = _count_task_group(tasks_dir, "done")
    total = active_count + planned_count + blocked_count + done_count

    task_ids = set()
    active_phase = _current_phase(goals)
    current_goal_task_ids = _current_goal_task_ids(goals)
    ledger_registry = omo_dir / "debt" / "registry.yaml"
    ledger = None
    metrics = None
    debt_items = None
    debt_generated_ref_flags: list[str] = []
    debt_generated_ref_detail_refs: dict[str, dict[str, object]] = {}
    done_task_ids: set[str] = set()
    for group in ("active", "blocked", "done"):
        # rglob 递归, 命中 p43/ 等子目录的归档副本
        for task_file in (tasks_dir / group).rglob("*.yaml"):
            task = _load_yaml(task_file)
            task_id = task.get("id")
            if task_id:
                task_phase = task.get("phase")
                if active_phase is not None and task_phase not in {None, active_phase}:
                    continue
                if task_phase is None and task_id not in current_goal_task_ids:
                    continue
                task_ids.add(task_id)
                if group == "done":
                    done_task_ids.add(task_id)
    if ledger_registry.exists():
        ledger = load_debt_ledger(omo_dir)
        debt_generated_ref_flags, debt_generated_ref_detail_refs = _debt_generated_ref_flags(omo_dir, ledger)

    goal_divergence_flags, divergence_detail_refs = _goal_divergence_flags(omo_dir, goals, task_ids, done_task_ids=done_task_ids)
    stale_dispatch_flags, stale_dispatch_refs = _stale_dispatch_flags(omo_dir, current_time)
    dangling_reference_flags, dangling_reference_refs = _dangling_reference_flags(omo_dir)
    divergence_flags = (
        goal_divergence_flags
        + _active_task_ref_flags(tasks_dir / "active")
        + stale_dispatch_flags
        + dangling_reference_flags
        + debt_generated_ref_flags
    )
    divergence_detail_refs = {
        **divergence_detail_refs,
        **stale_dispatch_refs,
        **dangling_reference_refs,
        **debt_generated_ref_detail_refs,
    }
    for detail_name in ("missing_goal_tasks", "orphaned_tasks", "stale_dispatches", "dangling_refs", "debt_generated_refs"):
        if detail_name not in divergence_detail_refs:
            _clear_divergence_detail_artifact(omo_dir, detail_name)
    task_gate_summary, promotion_blockers = _task_gate_summary(omo_dir, divergence_flags)
    divergence_triage_summary = _divergence_triage_summary(divergence_flags, _load_triage_rules(omo_dir))

    if isinstance(goal_phase, int):
        state["current_phase"] = goal_phase
    if isinstance(goal_wave, int):
        state["current_wave"] = goal_wave
    if isinstance(goal_status, str):
        state["phase_status"] = goal_status
    if isinstance(goal_next_milestone, str):
        state["next_milestone"] = goal_next_milestone
    if isinstance(goal_phase, int) and isinstance(goal_status, str):
        if goal_status == "active" and isinstance(goal_wave, int):
            state[f"phase{goal_phase}_status"] = f"wave{goal_wave}_active"
        else:
            state[f"phase{goal_phase}_status"] = goal_status

    state["active_tasks"] = active_count
    state["planned_tasks"] = planned_count
    state["blocked_tasks"] = blocked_count
    state["completed_tasks"] = done_count
    state["total_tasks"] = total
    raw_health = _parse_health_score(test_output, float(state.get("health_score_raw", state.get("health_score", 0.0))))
    if ledger_registry.exists():
        debt_items = {
            item.id: {
                "weight": item.weight,
                "desc": item.title,
            }
            for item in ledger.items
        }
        metrics = compute_debt_metrics(
            ledger.items,
            now=current_time.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            repo_root=omo_dir.parent,
        )
        resolved = set(metrics.closed_item_ids)
    else:
        resolved = set(state.get("resolved_debt_items", []))
        from omo.omo_debt_weight import DEBT_ITEMS
        debt_items = DEBT_ITEMS
    dw = compute_debt_weight(resolved, debt_items=debt_items)
    # X-Plane 接入(档位②): X 轴探活折扣。机制探不到活 → 给 health 打折,
    # 戳破"测试绿=系统健康"假象。故障降级: 任何探活异常 factor=1.0,
    # 绝不让 X-Plane 拖垮健康同步(健康同步必须 anti-fragile)。
    # xplane_factor 入参支持依赖注入:测试可显式传 1.0 隔离 X 轴以保持确定性。
    # 生产 CLI 把 xplane_factor 显式传 None 触发实时探活;默认 1.0 兼容直接 import 调用方。
    if xplane_factor is None:
        try:
            from omo.omo_xplane import compute_xplane_score

            # 全量探活(quick=False): 跑 command/http/counter 型,拿到真实覆盖率。
            # quick=True 只探 jsonl(只读、秒级),覆盖率仅 ~10%,会严重低估 X 轴。
            _xp = compute_xplane_score(quick=False)
            xplane_factor = float(_xp.get("xplane_factor", 1.0))
            state["xplane_score"] = _xp.get("xplane_score", 0.0)
            state["xplane_coverage"] = _xp.get("overall_coverage", 0.0)
        except Exception:  # noqa: BLE001 — X-Plane 故障不得阻断健康同步
            xplane_factor = 1.0
    xplane_factor = xplane_factor or 1.0  # NaN/None 终极兜底,保证 health 公式总有合法值
    state["health_score_raw"] = raw_health
    state["debt_weight"] = dw
    state["xplane_factor"] = xplane_factor
    # SSOT: health_score 的权威写入者是 bin/compass_radar.py (基于 anomalies).
    # sync_omo_state 只提供债务/X-Plane 调整后的参考值,避免覆盖权威健康分.
    state["debt_adjusted_health_score"] = round(raw_health * dw * xplane_factor, 2)
    if ledger and metrics:
        state["debt_registry_ref"] = ledger.registry_ref
        state["debt_dashboard_ref"] = ledger.dashboard_ref
        state["debt_review_pack_ref"] = ledger.review_pack_ref
        state["debt_reporting_ref"] = ledger.reporting_ref
        state["debt_metrics"] = {
            "debt_health": metrics.debt_health,
            "classification_entropy": metrics.classification_entropy,
            "state_entropy": metrics.state_entropy,
            "pointer_entropy": metrics.pointer_entropy,
            "time_entropy": metrics.time_entropy,
            "backlog_pressure": metrics.backlog_pressure,
            "coupling_load": metrics.coupling_load,
        }
        state["debt_watchlist_count"] = metrics.debt_watchlist_count
        state["debt_gate_count"] = metrics.debt_gate_count
        state["resolved_debt_items"] = sorted(resolved)
    state["debt_weight_items"] = debt_summary(resolved, debt_items=debt_items)
    state["divergence_flags"] = divergence_flags
    state["divergence_detail_refs"] = divergence_detail_refs
    state["task_gate_summary"] = task_gate_summary
    state["promotion_blockers"] = promotion_blockers
    state["divergence_triage_summary"] = divergence_triage_summary
    omo_ref = _omo_ref(omo_dir)
    state["next_active_tasks"] = _queue_preview(tasks_dir / "active", state.get("next_active_tasks"), omo_ref, "active")
    state["next_planned_tasks"] = _queue_preview(tasks_dir / "planned", state.get("next_planned_tasks"), omo_ref, "planned")
    if health_snapshot:
        state["runtime_health_summary"] = summarize_system_health_snapshot(health_snapshot)
    else:
        state.pop("runtime_health_summary", None)
    state["updated_at"] = current_time.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    state.pop("active_extras", None)

    validate_system_state(state)
    _write_yaml(state_path, state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(prog="sync-omo-state")
    parser.add_argument("--omo-dir", default=".omo", help="Path to the .omo directory")
    parser.add_argument("--test-output-file", help="Optional file containing test output to derive health_score")
    parser.add_argument("--now", help="Optional ISO8601 timestamp override for deterministic syncs")
    args = parser.parse_args()

    test_output = None
    if args.test_output_file:
        test_output = Path(args.test_output_file).read_text(encoding="utf-8")

    sync_state(Path(args.omo_dir), test_output=test_output, now=args.now, xplane_factor=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
