#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    from scripts.omo_admission import evaluate_worker_envelope, request_conditional_approval
    from scripts.omo_io import write_text_atomic, write_yaml_atomic
    from scripts.omo_handoff_index import write_handoff_index
    from scripts.omo_metrics import write_worker_utilization_summary
    from scripts.omo_promotion_history import build_promotion_history
    from scripts.omo_promotion_readiness import (
        build_promotion_readiness_packet,
        render_promotion_readiness_markdown,
    )
    from scripts.omo_rules import evaluate_rule_bundle
    from scripts.omo_rollout import accept_rollout_envelope, evaluate_rollout_envelope
    from scripts.omo_redaction import redact_sensitive_text
    from scripts.omo_task_schema import validate_active_tasks, validate_planned_tasks, validate_task_file
except ModuleNotFoundError:
    from omo_admission import evaluate_worker_envelope, request_conditional_approval
    from omo_io import write_text_atomic, write_yaml_atomic
    from omo_handoff_index import write_handoff_index
    from omo_metrics import write_worker_utilization_summary
    from omo_promotion_history import build_promotion_history
    from omo_promotion_readiness import build_promotion_readiness_packet, render_promotion_readiness_markdown
    from omo_rules import evaluate_rule_bundle
    from omo_rollout import accept_rollout_envelope, evaluate_rollout_envelope
    from omo_redaction import redact_sensitive_text
    from omo_task_schema import validate_active_tasks, validate_planned_tasks, validate_task_file


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, data: dict) -> None:
    write_yaml_atomic(path, data)


def _find_task_file(active_dir: Path, task_id: str) -> Path:
    for task_file in active_dir.glob("*.yaml"):
        task = _load_yaml(task_file)
        if task.get("id") == task_id:
            return task_file
    raise FileNotFoundError(f"Task not found in active/: {task_id}")


def _find_planned_task_file(planned_dir: Path, task_id: str) -> Path:
    for task_file in planned_dir.glob("*.yaml"):
        task = _load_yaml(task_file)
        if task.get("id") == task_id:
            return task_file
    raise FileNotFoundError(f"Task not found in planned/: {task_id}")


def _find_dispatch_file(runs_dir: Path, dispatch_id: str) -> Path:
    path = runs_dir / f"{dispatch_id}-dispatch.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Dispatch not found: {dispatch_id}")
    return path


def _worker_command(registry: dict, worker_id: str, transport: str) -> str:
    for worker in registry.get("workers", []):
        if worker.get("id") == worker_id:
            return worker["transports"][transport]["command"]
    raise KeyError(f"Worker not registered: {worker_id}")


def _append_unique(items: list[str], values: list[str]) -> list[str]:
    result = list(items)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _omo_path(root: Path, omo_dir: str | Path = ".omo") -> Path:
    return root / Path(omo_dir)


def collect_worker_status(root: Path, omo_dir: str | Path = ".omo") -> dict[str, object]:
    active_dir = _omo_path(root, omo_dir) / "tasks" / "active"
    runs: list[dict[str, object]] = []

    for task_file in sorted(active_dir.glob("*.yaml")):
        task = _load_yaml(task_file)
        run_ref = task.get("run_ref")
        if not run_ref:
            continue

        dispatch_path = root / run_ref
        if not dispatch_path.exists():
            continue

        dispatch = _load_yaml(dispatch_path)
        runs.append(
            {
                "task_id": dispatch.get("task_id", task.get("id")),
                "worker_id": dispatch.get("worker_id"),
                "dispatch_state": dispatch.get("dispatch_state"),
                "checkpoint_refs": dispatch.get("execution", {}).get("checkpoint_refs", []),
                "reclaim_ref": dispatch.get("reclaim", {}).get("note_ref"),
                "review_ref": dispatch.get("handoff", {}).get("output_summary_ref"),
                "lease": dispatch.get("lease", {}),
            }
        )

    return {
        "active_dispatches": len(runs),
        "runs": runs,
    }


def update_dispatch_checkpoint(
    root: Path,
    dispatch_id: str,
    completed_step: str,
    changed_files: list[str],
    note: str,
    now: str | None = None,
    omo_dir: str | Path = ".omo",
) -> dict[str, object]:
    dispatch_path = _find_dispatch_file(_omo_path(root, omo_dir) / "workers" / "runs", dispatch_id)
    dispatch = _load_yaml(dispatch_path)
    checkpoint_ref = dispatch.get("execution", {}).get("checkpoint_refs", [None])[-1]
    if not checkpoint_ref:
        raise ValueError(f"dispatch {dispatch_id} has no checkpoint ref")

    timestamp = now or _utc_now()
    changed_file_lines = [f"- `{path}`" for path in changed_files] or ["- None"]
    checkpoint_lines = [
        "# Checkpoint Note",
        "",
        "## Last completed step",
        "",
        completed_step,
        "",
        "## Changed files",
        "",
        *changed_file_lines,
        "",
        "## Operator note",
        "",
        note,
        "",
    ]
    write_text_atomic(root / checkpoint_ref, "\n".join(checkpoint_lines))

    dispatch["dispatch_state"] = "checkpointed"
    dispatch["lease"]["last_checkpoint_at"] = timestamp
    dispatch["lease"]["last_material_write_at"] = timestamp
    _write_yaml(dispatch_path, dispatch)
    return dispatch


def scan_runtime_watchdog(root: Path, now: str | None = None, omo_dir: str | Path = ".omo") -> dict[str, object]:
    current_time = _parse_iso8601(now) or datetime.now(timezone.utc)
    status = collect_worker_status(root, omo_dir=omo_dir)
    runs: list[dict[str, object]] = []
    counts = {"healthy": 0, "warning": 0, "stale": 0, "reclaim_due": 0}

    for run in status["runs"]:
        lease = run.get("lease", {})
        last_seen = _parse_iso8601(lease.get("last_material_write_at")) or _parse_iso8601(lease.get("last_checkpoint_at"))
        age_seconds = int((current_time - last_seen).total_seconds()) if last_seen else None
        health = "healthy"
        if age_seconds is not None:
            if age_seconds >= lease.get("reclaim_after_seconds", 0):
                health = "reclaim_due"
            elif age_seconds >= lease.get("lease_expired_after_seconds", 0):
                health = "stale"
            elif age_seconds >= lease.get("warning_after_seconds", 0):
                health = "warning"
        counts[health] += 1
        runs.append(
            {
                **run,
                "age_seconds": age_seconds,
                "health": health,
            }
        )

    return {"counts": counts, "runs": runs}


def _build_launch_argv(registry: dict, worker_id: str, transport: str, prompt_text: str) -> list[str]:
    sentinel = "__OMO_PROMPT__"
    template = _worker_command(registry, worker_id, transport).format(prompt=sentinel)
    argv = shlex.split(template)
    forbidden_fragments = ("&&", "||", "|")
    for index, arg in enumerate(argv):
        if index > 0 and argv[index - 1] == "-c":
            continue
        if any(fragment in arg for fragment in forbidden_fragments):
            raise ValueError(f"unsafe worker command template: {template}")
        if ";" in arg and arg != ";" and not arg.startswith("-c"):
            raise ValueError(f"unsafe worker command template: {template}")
    return [prompt_text if arg == sentinel else arg for arg in argv]


def dispatch_task(
    root: Path,
    task_id: str,
    worker_id: str,
    allowed_write_paths: list[str],
    launch: bool = False,
    transport: str = "cli_prompt",
    prior_evidence: list[str] | None = None,
    prompt_addendum: list[str] | None = None,
    omo_dir: str | Path = ".omo",
) -> dict[str, str]:
    omo = _omo_path(root, omo_dir)
    omo_ref = Path(omo_dir)
    task_file = _find_task_file(omo / "tasks" / "active", task_id)
    validation_errors = validate_task_file(task_file)
    if validation_errors:
        raise ValueError("; ".join(validation_errors))
    task = _load_yaml(task_file)
    registry = _load_yaml(omo / "workers" / "registry.yaml")

    dispatch_id = f"{task_id.lower()}-{worker_id}-{_timestamp_slug()}"
    run_dir = omo / "workers" / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)

    dispatch_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-dispatch.yaml"
    envelope_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-envelope.yaml"
    prompt_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-prompt.md"
    checkpoint_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-checkpoint.md"
    reclaim_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-reclaim.md"
    review_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-review.md"
    stdout_path = omo_ref / "workers" / "runs" / f"{dispatch_id}-stdout.log"

    source_docs = task.get("source_docs", [])
    deliverables = task.get("deliverables", [])
    allowed_paths = list(allowed_write_paths)
    recovery_lines = list(prompt_addendum or [])
    prompt = "\n".join(
        [
            "# Worker Prompt Contract",
            "",
            f"WORKER_ID: `{worker_id}`",
            f"TASK_ID: `{task_id}`",
            f"TRANSPORT: `{transport}`",
            "READ_BUDGET: `5`",
            "",
            "## Mission",
            "",
            task.get("title", task_id),
            "",
            "## Task SSOT",
            "",
            f"- Task YAML: `{task_file.relative_to(root)}`",
            *(f"- Source doc: `{doc}`" for doc in source_docs),
            "",
            "## Constraints",
            "",
            *(f"- You may write to `{path}`" for path in allowed_paths),
            f"- You may write to `{task_file.relative_to(root)}`",
            f"- You may write to `{review_path}`",
            "- Do not modify global state files.",
            "- Do not mark the task `done`.",
            "",
            "## Required deliverables",
            "",
            *(
                f"- Required deliverable: `{path}`"
                for path in deliverables
            ),
            "- Updating only the review note is not sufficient when required deliverables are listed.",
            *recovery_lines,
        ]
    )
    write_text_atomic(root / prompt_path, prompt + "\n")
    write_text_atomic(
        root / checkpoint_path,
        "# Checkpoint Note\n\n## Last completed step\n\nTBD\n\n## Changed files\n\n- None yet\n",
    )
    write_text_atomic(
        root / reclaim_path,
        "# Reclaim Note\n\n## Reclaim reason\n\nTBD\n\n## Required successor context\n\n- Review the checkpoint note first.\n",
    )
    write_text_atomic(
        root / review_path,
        "# Review Note\n\n## Summary of work done\n\nTBD\n",
    )

    envelope = {
        "version": 1,
        "task_id": task_id,
        "worker_id": worker_id,
        "transport_mode": transport,
        "run_ref": str(dispatch_path),
        "knowledge_refs": source_docs,
        "handoff_refs": [str(prompt_path), str(checkpoint_path), str(review_path), str(reclaim_path)],
        "objective": task.get("title", task_id),
        "task_yaml": str(task_file.relative_to(root)),
        "inputs": {
            "source_docs": source_docs,
            "required_context": [str(task_file.relative_to(root))],
            "prior_evidence": list(prior_evidence or []),
        },
        "outputs": {
            "required_deliverables": deliverables,
        },
        "scope": {
            "allowed_write_paths": allowed_paths,
            "forbidden_write_paths": [
                ".omo/state/system.yaml",
                ".omo/goals/current.yaml",
                "convergence.yaml",
            ],
            "non_goals": ["Do not modify global state files"],
        },
        "execution_policy": {
            "read_budget": 5,
            "heartbeat_interval_seconds": 300,
            "warning_after_seconds": 900,
            "lease_expired_after_seconds": 1200,
            "reclaim_after_seconds": 1800,
            "checkpoint_required": True,
            "require_partial_output_when_stuck": True,
        },
        "gates": {
            "allowed_operation_level": task.get("allowed_operation_level", "L0"),
            "may_prepare_levels": [],
            "human_approval_required_for": [],
            "approval_ref": task.get("approval_ref"),
            "sensitive_capabilities_blocked": True,
        },
        "knowledge_contract": {
            "output_summary_required": True,
            "changed_files_required": True,
            "evidence_required": True,
            "unresolved_risks_required": True,
            "next_handoff_required": True,
        },
        "review": {
            "closeout_owner": "coordinator",
            "worker_may_set_review": True,
            "worker_may_set_done": False,
            "worker_may_set_blocked": False,
        },
    }
    _write_yaml(root / envelope_path, envelope)

    launch_command = _worker_command(registry, worker_id, transport).format(prompt=f"<prompt:{prompt_path}>")
    dispatch = {
        "version": 1,
        "dispatch_id": dispatch_id,
        "task_id": task_id,
        "worker_id": worker_id,
        "transport_mode": transport,
        "run_ref": str(dispatch_path),
        "dispatch_state": "dispatched",
        "coordinator": "copilot-cli",
        "launched_at": _utc_now(),
        "lease": {
            "heartbeat_interval_seconds": 300,
            "warning_after_seconds": 900,
            "lease_expired_after_seconds": 1200,
            "reclaim_after_seconds": 1800,
            "last_checkpoint_at": None,
            "last_material_write_at": None,
        },
        "inputs": {
            "task_yaml": str(task_file.relative_to(root)),
            "envelope_file": str(envelope_path),
            "prompt_file": str(prompt_path),
            "source_docs": source_docs,
        },
        "execution": {
            "launch_command": launch_command,
            "approval_ref": task.get("approval_ref"),
            "session_ref": None,
            "log_ref": str(stdout_path),
            "checkpoint_refs": [str(checkpoint_path)],
        },
        "handoff": {
            "output_summary_ref": str(review_path),
            "evidence_paths": [],
            "unresolved_risks": [],
            "next_handoff": None,
        },
        "reclaim": {
            "required": False,
            "reason": None,
            "reclaimed_at": None,
            "successor_worker_id": None,
            "successor_dispatch_id": None,
            "note_ref": str(reclaim_path),
        },
    }
    _write_yaml(root / dispatch_path, dispatch)

    task["status"] = "in_progress"
    task["assigned_to"] = worker_id
    task["dispatch_id"] = dispatch_id
    task["run_ref"] = str(dispatch_path)
    task["review_ref"] = str(review_path)
    task["started_at"] = task.get("started_at") or _utc_now()
    task["knowledge_refs"] = _append_unique(task.get("knowledge_refs", []), source_docs)
    task["handoff_refs"] = _append_unique(
        task.get("handoff_refs", []),
        [str(envelope_path), str(prompt_path), str(checkpoint_path)],
    )
    _write_yaml(task_file, task)

    if launch:
        prompt_text = (root / prompt_path).read_text(encoding="utf-8")
        argv = _build_launch_argv(registry, worker_id, transport, prompt_text)
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
        write_text_atomic(root / stdout_path, redact_sensitive_text((result.stdout or "") + (result.stderr or "")))

    return {
        "dispatch_id": dispatch_id,
        "dispatch_path": str(dispatch_path),
        "envelope_path": str(envelope_path),
        "prompt_path": str(prompt_path),
        "checkpoint_path": str(checkpoint_path),
        "reclaim_path": str(reclaim_path),
        "review_path": str(review_path),
    }


def reclaim_task(
    root: Path,
    task_id: str,
    successor_worker_id: str,
    allowed_write_paths: list[str],
    reason: str,
    launch: bool = False,
    transport: str = "cli_prompt",
    omo_dir: str | Path = ".omo",
) -> dict[str, str]:
    active_dir = _omo_path(root, omo_dir) / "tasks" / "active"
    task_file = _find_task_file(active_dir, task_id)
    task = _load_yaml(task_file)
    run_ref = task.get("run_ref")
    if not run_ref:
        raise ValueError(f"Task has no active run to reclaim: {task_id}")

    prior_dispatch_path = root / run_ref
    prior_dispatch = _load_yaml(prior_dispatch_path)
    checkpoint_refs = list(prior_dispatch.get("execution", {}).get("checkpoint_refs", []))
    reclaim_ref = prior_dispatch.get("reclaim", {}).get("note_ref")
    reclaim_note_path = root / reclaim_ref if reclaim_ref else None

    if reclaim_note_path is not None:
        write_text_atomic(
            reclaim_note_path,
            "\n".join(
                [
                    "# Reclaim Note",
                    "",
                    "## Reclaim reason",
                    "",
                    reason,
                    "",
                    "## Required successor context",
                    "",
                    *(f"- Review checkpoint: `{ref}`" for ref in checkpoint_refs),
                    *(f"- Review reclaim note: `{reclaim_ref}`" for _ in [0] if reclaim_ref),
                    "",
                    f"## Successor worker",
                    "",
                    successor_worker_id,
                    "",
                ]
            )
            + "\n",
        )

    prior_dispatch["dispatch_state"] = "reclaimed"
    prior_dispatch["reclaim"]["required"] = True
    prior_dispatch["reclaim"]["reason"] = reason
    prior_dispatch["reclaim"]["reclaimed_at"] = _utc_now()
    prior_dispatch["reclaim"]["successor_worker_id"] = successor_worker_id
    _write_yaml(prior_dispatch_path, prior_dispatch)

    prior_evidence = checkpoint_refs + ([reclaim_ref] if reclaim_ref else [])
    prompt_addendum = [
        "",
        "## Recovery context",
        "",
        f"- Reclaim reason: {reason}",
        *(f"- Resume from checkpoint: `{ref}`" for ref in checkpoint_refs),
        *(f"- Review reclaim handoff: `{reclaim_ref}`" for _ in [0] if reclaim_ref),
        "- Continue from the recorded checkpoint instead of restarting the task.",
    ]
    successor = dispatch_task(
        root,
        task_id=task_id,
        worker_id=successor_worker_id,
        allowed_write_paths=allowed_write_paths,
        launch=launch,
        transport=transport,
        prior_evidence=prior_evidence,
        prompt_addendum=prompt_addendum,
        omo_dir=omo_dir,
    )

    prior_dispatch = _load_yaml(prior_dispatch_path)
    prior_dispatch["reclaim"]["successor_dispatch_id"] = successor["dispatch_id"]
    _write_yaml(prior_dispatch_path, prior_dispatch)
    return successor


def _worker_gc(root: Path, dry_run: bool = False, retain: int = 50, omo_dir: str | Path = ".omo") -> int:
    """清理旧的 worker dispatch 运行文件。

    Args:
        root: Workspace 根目录
        dry_run: 仅列出拟删除文件，不实际删除
        retain: 保留的最新 dispatch 数目

    Returns:
        0 表示成功，1 表示有错误
    """
    runs_dir = _omo_path(root, omo_dir) / "workers" / "runs"
    if not runs_dir.exists():
        print("No runs directory found at", runs_dir)
        return 0

    # 收集所有 dispatch 文件，按 dispatch_id 中的 timestamp 分组
    dispatch_files: dict[str, list[Path]] = {}
    for f in runs_dir.iterdir():
        if f.is_file():
            # dispatch_id 通常为 dispatch-{task_id}-{timestamp} 格式
            name = f.stem
            # 去掉可能的后缀变体（如 -prompt, -envelope, -review 等后缀）
            base = name.split(".")[0]
            # 尝试提取 dispatch_id（第一个词和最后一个时间戳之间）
            # 格式举例: dispatch-TASK-1-20260530T161437 → 提取 dispatch-TASK-1-20260530T161437
            # 或者带后缀: dispatch-TASK-1-20260530T161437-prompt → 也属于同一组
            # 简单做法：按文件名前缀（去掉最后一个 - 后缀）分组
            parts = name.rsplit("-", 1)
            if len(parts) > 1 and parts[1] in ("prompt", "envelope", "review", "dispatch"):
                group_key = parts[0]
            else:
                group_key = name
            dispatch_files.setdefault(group_key, []).append(f)

    # 按组键名排序（时间戳在键名末尾，排序即按时间）
    sorted_groups = sorted(dispatch_files.keys())

    if len(sorted_groups) <= retain:
        print(f"Total dispatch runs: {len(sorted_groups)} (≤ retain={retain}, nothing to clean)")
        return 0

    to_delete = sorted_groups[:-retain]
    total_files = 0
    for group_key in to_delete:
        files = dispatch_files[group_key]
        total_files += len(files)
        if dry_run:
            print(f"[DRY-RUN] Would delete {len(files)} file(s) for dispatch {group_key}:")
            for f in files:
                print(f"  {f}")
        else:
            for f in files:
                f.unlink()
            print(f"Deleted {len(files)} file(s) for dispatch {group_key}")

    print(f"GC complete: retained {retain} dispatch runs, "
          f"cleaned {len(to_delete)} old runs ({total_files} files)")
    return 0


def _print_worker_status(root: Path, omo_dir: str | Path = ".omo") -> int:
    status = collect_worker_status(root, omo_dir=omo_dir)
    print(f"active_dispatches={status['active_dispatches']}")
    for run in status["runs"]:
        print(
            f"{run['task_id']} worker={run['worker_id']} "
            f"state={run['dispatch_state']} checkpoints={len(run['checkpoint_refs'])} "
            f"reclaim={run['reclaim_ref']}"
        )
    return 0


def _print_worker_watchdog(root: Path, now: str | None = None, omo_dir: str | Path = ".omo") -> int:
    watchdog = scan_runtime_watchdog(root, now=now, omo_dir=omo_dir)
    counts = watchdog["counts"]
    print(
        f"healthy={counts['healthy']} warning={counts['warning']} "
        f"stale={counts['stale']} reclaim_due={counts['reclaim_due']}"
    )
    for run in watchdog["runs"]:
        print(
            f"{run['task_id']} worker={run['worker_id']} state={run['dispatch_state']} "
            f"health={run['health']} age_seconds={run['age_seconds']}"
        )
    return 0


def _print_worker_admission_eval(root: Path, envelope_ref: str, matrix_ref: str | None = None) -> int:
    result = evaluate_worker_envelope(
        root,
        Path(envelope_ref),
        matrix_ref=Path(matrix_ref) if matrix_ref else None,
    )
    print(
        f"action={result['action']} membership={result['membership_ref']} "
        f"decision={result['decision']} approval_required={result['approval_required']}"
    )
    return 0


def _request_worker_admission_approval(
    root: Path,
    envelope_ref: str,
    requested_by: str,
    now: str,
) -> int:
    result = request_conditional_approval(root, Path(envelope_ref), requested_by=requested_by, now=now)
    print(f"proposal={result['proposal_id']} approval_ref={result['approval_ref']} decision={result['decision']}")
    return 0


def _print_worker_rollout_eval(root: Path, envelope_ref: str) -> int:
    result = evaluate_rollout_envelope(root, Path(envelope_ref))
    print(
        f"action={result['action']} approval={result['approval_status']} "
        f"decision={result['decision']} acceptance_ready={result['acceptance_ready']}"
    )
    return 0


def _accept_worker_rollout(root: Path, envelope_ref: str, accepted_by: str, now: str) -> int:
    result = accept_rollout_envelope(root, Path(envelope_ref), accepted_by=accepted_by, now=now)
    print(f"acceptance_ref={result['acceptance_ref']} decision={result['decision']}")
    return 0


def _print_worker_rules_eval(root: Path, envelope_ref: str) -> int:
    result = evaluate_rule_bundle(root, Path(envelope_ref))
    delivery_contract = result.get("delivery_contract_ref")
    delivery_segment = f" delivery_contract={delivery_contract}" if delivery_contract else ""
    print(
        f"action={result['action']} registry={result['registry_ref']} "
        f"data_policy={result['data_policy_ref']}{delivery_segment} "
        f"runtime_boundary={result['runtime_boundary_ref']}"
    )
    return 0


def _promotion_eval(root: Path, task_id: str, omo_dir: str | Path = ".omo") -> dict[str, object]:
    omo = _omo_path(root, omo_dir)
    goals = _load_yaml(omo / "goals" / "current.yaml")
    task_file = _find_planned_task_file(omo / "tasks" / "planned", task_id)
    task = _load_yaml(task_file)
    active_target = omo / "tasks" / "active" / task_file.name

    checks = {
        "queue_membership_ok": True,
        "status_ok": task.get("status") in {"candidate", "pending"},
        "phase_ok": task.get("phase") == int(goals["phase"]) + 1,
        "approval_ready": (not task.get("human_approval_required")) or bool(task.get("approval_ref")),
        "target_path_clear": not active_target.exists(),
    }

    active_ready_errors = validate_task_file(task_file)
    checks["active_schema_ready"] = not active_ready_errors

    blockers: list[str] = []
    if not checks["status_ok"]:
        blockers.append("status_invalid")
    if not checks["phase_ok"]:
        blockers.append("phase_mismatch")
    if not checks["approval_ready"]:
        blockers.append("approval_missing")
    if not checks["target_path_clear"]:
        blockers.append("target_path_exists")
    if not checks["active_schema_ready"]:
        blockers.append("active_schema_invalid")

    return {
        "task_id": task_id,
        "task_ref": str(task_file.relative_to(root)),
        "eligible": not blockers,
        "blockers": blockers,
        "checks": checks,
        "errors": active_ready_errors,
    }


def _print_task_promotion_eval(root: Path, task_id: str, omo_dir: str | Path = ".omo") -> int:
    result = _promotion_eval(root, task_id, omo_dir=omo_dir)
    print(
        f"task_id={result['task_id']} eligible={str(result['eligible']).lower()} "
        f"blockers={','.join(result['blockers']) or 'none'}"
    )
    return 0 if result["eligible"] else 1


def _promotion_stamp(now: str) -> str:
    return now.replace(":", "-")


def _sync_omo_state(root: Path, omo_dir: str | Path) -> None:
    subprocess.run(
        ["python3", "scripts/sync_omo_state.py", "--omo-dir", str(omo_dir)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _apply_task_promotion(root: Path, task_id: str, promoted_by: str, now: str, omo_dir: str | Path = ".omo") -> int:
    result = _promotion_eval(root, task_id, omo_dir=omo_dir)
    if not result["eligible"]:
        print(f"task_id={task_id} eligible=false blockers={','.join(result['blockers'])}")
        return 1

    omo = _omo_path(root, omo_dir)
    planned_path = root / result["task_ref"]
    active_path = omo / "tasks" / "active" / planned_path.name
    task = _load_yaml(planned_path)
    stamp = _promotion_stamp(now)
    envelope_rel = Path(omo_dir) / "workers" / "runs" / f"{task_id}-promotion-{stamp}.yaml"
    envelope_path = root / envelope_rel
    envelope = {
        "version": 1,
        "promotion_id": f"{task_id}-promotion-{stamp}",
        "task_id": task_id,
        "task_ref_before": str(Path(omo_dir) / "tasks" / "planned" / planned_path.name),
        "task_ref_after": str(Path(omo_dir) / "tasks" / "active" / planned_path.name),
        "promotion_status": "approved",
        "promoted_by": promoted_by,
        "promoted_at": now,
        "phase_gate": {
            "current_phase": int(_load_yaml(omo / "goals" / "current.yaml")["phase"]),
            "target_phase": task["phase"],
            "allowed_by_rule": True,
        },
        "approval": {
            "required": bool(task.get("human_approval_required")),
            "approval_ref": task.get("approval_ref"),
        },
        "checks": result["checks"],
        "rollback": {
            "supported": True,
            "rollback_action": "move task back to planned and rerun sync",
        },
        "refs": {
            "state_ref": str(Path(omo_dir) / "state" / "system.yaml"),
            "goals_ref": str(Path(omo_dir) / "goals" / "current.yaml"),
        },
    }
    _write_yaml(envelope_path, envelope)

    original_handoffs = list(task.get("handoff_refs", []))
    task["handoff_refs"] = _append_unique(original_handoffs, [str(envelope_rel)])
    _write_yaml(planned_path, task)

    active_path.parent.mkdir(parents=True, exist_ok=True)
    planned_path.replace(active_path)
    try:
        _sync_omo_state(root, omo_dir)
    except subprocess.CalledProcessError:
        active_task = _load_yaml(active_path)
        active_task["handoff_refs"] = original_handoffs
        _write_yaml(active_path, active_task)
        active_path.replace(planned_path)
        envelope_path.unlink(missing_ok=True)
        print(f"task_id={task_id} promoted=false blockers=sync_failed")
        return 1

    print(f"promotion_ref={envelope_rel} task_ref={Path(omo_dir) / 'tasks' / 'active' / planned_path.name}")
    return 0


def _write_task_promotion_history(root: Path, omo_dir: str | Path = ".omo", now: str | None = None) -> int:
    result = build_promotion_history(root, omo_dir=omo_dir, now=now or _utc_now())
    omo = _omo_path(root, omo_dir)
    current_yaml = omo / "workers" / "promotion" / "current.yaml"
    current_md = omo / "workers" / "promotion" / "current.md"
    _write_yaml(current_yaml, result["yaml"])
    write_text_atomic(current_md, result["markdown"])
    print(
        f"promotion_count={result['yaml']['promotion_count']} "
        f"latest_promotion_ref={result['yaml']['latest_promotion_ref']}"
    )
    return 0


def _promotion_readiness_entry(root: Path, task_path: Path, omo_dir: str | Path = ".omo") -> dict[str, object]:
    task = _load_yaml(task_path)
    eval_result = _promotion_eval(root, task["id"], omo_dir=omo_dir)
    return {
        "task_id": task["id"],
        "task_ref": eval_result["task_ref"],
        "phase": task["phase"],
        "status": task["status"],
        "risk_level": task["risk_level"],
        "allowed_operation_level": task["allowed_operation_level"],
        "human_approval_required": bool(task.get("human_approval_required")),
        "approval_ref": task.get("approval_ref"),
        "eligible": eval_result["eligible"],
        "blockers": eval_result["blockers"],
        "checks": eval_result["checks"],
        "errors": eval_result["errors"],
    }


def _write_task_promotion_readiness(root: Path, omo_dir: str | Path = ".omo", now: str | None = None) -> int:
    omo = _omo_path(root, omo_dir)
    goals = _load_yaml(omo / "goals" / "current.yaml")
    planned_dir = omo / "tasks" / "planned"
    entries = tuple(
        _promotion_readiness_entry(root, task_path, omo_dir=omo_dir)
        for task_path in sorted(planned_dir.glob("*.yaml"))
    )
    packet = build_promotion_readiness_packet(
        generated_at=now or _utc_now(),
        current_phase=int(goals["phase"]),
        tasks=entries,
    )
    readiness_dir = omo / "workers" / "promotion"
    readiness_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(readiness_dir / "readiness.yaml", packet)
    write_text_atomic(readiness_dir / "readiness.md", render_promotion_readiness_markdown(packet))
    print(f"ready_count={packet['ready_count']} blocked_count={packet['blocked_count']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="omo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    worker_parser = subparsers.add_parser("worker")
    worker_sub = worker_parser.add_subparsers(dest="worker_command", required=True)

    dispatch_parser = worker_sub.add_parser("dispatch")
    dispatch_parser.add_argument("task_id")
    dispatch_parser.add_argument("--worker", required=True, dest="worker_id")
    dispatch_parser.add_argument("--write-path", action="append", default=[], dest="write_paths")
    dispatch_parser.add_argument("--launch", action="store_true")
    dispatch_parser.add_argument("--transport", default="cli_prompt")
    dispatch_parser.add_argument("--omo-dir", default=".omo")

    reclaim_parser = worker_sub.add_parser("reclaim")
    reclaim_parser.add_argument("task_id")
    reclaim_parser.add_argument("--successor", required=True, dest="successor_worker_id")
    reclaim_parser.add_argument("--reason", required=True)
    reclaim_parser.add_argument("--write-path", action="append", default=[], dest="write_paths")
    reclaim_parser.add_argument("--launch", action="store_true")
    reclaim_parser.add_argument("--transport", default="cli_prompt")
    reclaim_parser.add_argument("--omo-dir", default=".omo")

    gc_parser = worker_sub.add_parser("gc")
    gc_parser.add_argument("--dry-run", action="store_true", help="Just list, don't delete")
    gc_parser.add_argument("--retain", type=int, default=50, help="Number of latest dispatch runs to retain")
    gc_parser.add_argument("--omo-dir", default=".omo")

    status_parser = worker_sub.add_parser("status")
    status_parser.add_argument("--omo-dir", default=".omo")
    baseline_parser = worker_sub.add_parser("baseline")
    baseline_parser.add_argument("--root", default=".")
    handoff_parser = worker_sub.add_parser("handoff-index")
    handoff_parser.add_argument("task_id")
    watchdog_parser = worker_sub.add_parser("watchdog")
    watchdog_parser.add_argument("--now")
    watchdog_parser.add_argument("--omo-dir", default=".omo")
    admission_parser = worker_sub.add_parser("admission-eval")
    admission_parser.add_argument("envelope_ref")
    admission_parser.add_argument("--matrix-ref")
    request_approval_parser = worker_sub.add_parser("admission-request-approval")
    request_approval_parser.add_argument("envelope_ref")
    request_approval_parser.add_argument("--requested-by", required=True)
    request_approval_parser.add_argument("--now", required=True)
    rules_eval_parser = worker_sub.add_parser("rules-eval")
    rules_eval_parser.add_argument("envelope_ref")
    rollout_eval_parser = worker_sub.add_parser("rollout-eval")
    rollout_eval_parser.add_argument("envelope_ref")
    rollout_accept_parser = worker_sub.add_parser("rollout-accept")
    rollout_accept_parser.add_argument("envelope_ref")
    rollout_accept_parser.add_argument("--accepted-by", required=True)
    rollout_accept_parser.add_argument("--now", required=True)

    task_parser = subparsers.add_parser("task")
    task_sub = task_parser.add_subparsers(dest="task_command", required=True)
    validate_parser = task_sub.add_parser("validate")
    validate_parser.add_argument("task_file", nargs="?")
    validate_parser.add_argument("--all-active", action="store_true")
    validate_parser.add_argument("--all-planned", action="store_true")
    promote_eval_parser = task_sub.add_parser("promote-eval")
    promote_eval_parser.add_argument("task_id")
    promote_eval_parser.add_argument("--omo-dir", default=".omo")
    promote_apply_parser = task_sub.add_parser("promote-apply")
    promote_apply_parser.add_argument("task_id")
    promote_apply_parser.add_argument("--promoted-by", required=True)
    promote_apply_parser.add_argument("--now", required=True)
    promote_apply_parser.add_argument("--omo-dir", default=".omo")
    promotion_history_parser = task_sub.add_parser("promotion-history")
    promotion_history_parser.add_argument("--omo-dir", default=".omo")
    promotion_history_parser.add_argument("--now")
    promotion_readiness_parser = task_sub.add_parser("promotion-readiness")
    promotion_readiness_parser.add_argument("--omo-dir", default=".omo")
    promotion_readiness_parser.add_argument("--now")

    args = parser.parse_args()

    if args.command == "worker" and args.worker_command == "dispatch":
        dispatch_task(
            Path.cwd(),
            task_id=args.task_id,
            worker_id=args.worker_id,
            allowed_write_paths=args.write_paths,
            launch=args.launch,
            transport=args.transport,
            omo_dir=args.omo_dir,
        )
        return 0

    if args.command == "worker" and args.worker_command == "reclaim":
        reclaim_task(
            Path.cwd(),
            task_id=args.task_id,
            successor_worker_id=args.successor_worker_id,
            allowed_write_paths=args.write_paths,
            reason=args.reason,
            launch=args.launch,
            transport=args.transport,
            omo_dir=args.omo_dir,
        )
        return 0

    if args.command == "worker" and args.worker_command == "gc":
        return _worker_gc(Path.cwd(), dry_run=args.dry_run, retain=args.retain, omo_dir=args.omo_dir)

    if args.command == "worker" and args.worker_command == "status":
        return _print_worker_status(Path.cwd(), omo_dir=args.omo_dir)

    if args.command == "worker" and args.worker_command == "baseline":
        print(write_worker_utilization_summary(Path(args.root).resolve()))
        return 0

    if args.command == "worker" and args.worker_command == "handoff-index":
        print(write_handoff_index(Path.cwd(), args.task_id))
        return 0

    if args.command == "worker" and args.worker_command == "watchdog":
        return _print_worker_watchdog(Path.cwd(), now=args.now, omo_dir=args.omo_dir)

    if args.command == "worker" and args.worker_command == "admission-eval":
        return _print_worker_admission_eval(Path.cwd(), args.envelope_ref, matrix_ref=args.matrix_ref)

    if args.command == "worker" and args.worker_command == "admission-request-approval":
        return _request_worker_admission_approval(Path.cwd(), args.envelope_ref, requested_by=args.requested_by, now=args.now)

    if args.command == "worker" and args.worker_command == "rules-eval":
        return _print_worker_rules_eval(Path.cwd(), args.envelope_ref)

    if args.command == "worker" and args.worker_command == "rollout-eval":
        return _print_worker_rollout_eval(Path.cwd(), args.envelope_ref)

    if args.command == "worker" and args.worker_command == "rollout-accept":
        return _accept_worker_rollout(Path.cwd(), args.envelope_ref, accepted_by=args.accepted_by, now=args.now)

    if args.command == "task" and args.task_command == "validate":
        if args.all_planned:
            results = validate_planned_tasks(Path.cwd())
            if not results:
                return 0
            for path, errors in results.items():
                print(path)
                for error in errors:
                    print(f"  - {error}")
            return 1

        if args.all_active or not args.task_file:
            results = validate_active_tasks(Path.cwd())
            if not results:
                return 0
            for path, errors in results.items():
                print(path)
                for error in errors:
                    print(f"  - {error}")
            return 1

        errors = validate_task_file(Path(args.task_file))
        if not errors:
            return 0
        for error in errors:
            print(error)
        return 1

    if args.command == "task" and args.task_command == "promote-eval":
        return _print_task_promotion_eval(Path.cwd(), args.task_id, omo_dir=args.omo_dir)

    if args.command == "task" and args.task_command == "promote-apply":
        return _apply_task_promotion(
            Path.cwd(),
            args.task_id,
            promoted_by=args.promoted_by,
            now=args.now,
            omo_dir=args.omo_dir,
        )

    if args.command == "task" and args.task_command == "promotion-history":
        return _write_task_promotion_history(Path.cwd(), omo_dir=args.omo_dir, now=args.now)

    if args.command == "task" and args.task_command == "promotion-readiness":
        return _write_task_promotion_readiness(Path.cwd(), omo_dir=args.omo_dir, now=args.now)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
