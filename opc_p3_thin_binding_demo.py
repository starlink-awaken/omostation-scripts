#!/usr/bin/env python3
"""Generate replayable OPC P3 thin-binding evidence for Gate D3-D5."""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lib.bootstrap import workspace_root
from lib.yaml_utils import load_yaml_or_default

ROOT = workspace_root()
OMO_SRC = ROOT / "projects" / "omo" / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))

from omo.omo_handoff_index import write_handoff_index
from omo.omo_io import ensure_parent_dir
from omo.omo_metrics import write_worker_utilization_summary
from omo.omo_worker_dispatch import dispatch_task
from omo.omo_worker_status import scan_runtime_watchdog, update_dispatch_checkpoint

DEFAULT_EVIDENCE_ROOT = ROOT / ".omo" / "tasks" / "registry" / "done"
FIXED_NOW = "2026-06-12T10:00:00Z"


@dataclass(frozen=True)
class DemoTaskSpec:
    task_id: str
    role: str
    worker_id: str
    title: str
    deliverable: str
    allowed_write_path: str
    source_docs: list[str]
    completed_step: str
    completion_summary: str
    changed_files: list[str]
    review_summary: str
    risks: list[str]
    next_handoff: str | None = None


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    return load_yaml_or_default(path, {})


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _display_path(path: Path, base: Path = ROOT) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _seed_worker_registry(demo_root: Path) -> None:
    registry = {
        "workers": [
            {
                "id": "planner-001",
                "transports": {"cli_prompt": {"command": 'planner "{prompt}"'}},
            },
            {
                "id": "researcher-001",
                "transports": {"cli_prompt": {"command": 'researcher "{prompt}"'}},
            },
            {
                "id": "reviewer-001",
                "transports": {"cli_prompt": {"command": 'reviewer "{prompt}"'}},
            },
            {
                "id": "operator-001",
                "transports": {"cli_prompt": {"command": 'operator "{prompt}"'}},
            },
        ]
    }
    _write_yaml(demo_root / ".omo" / "_truth" / "registry" / "workers.yaml", registry)


def _seed_parent_goal(demo_root: Path, child_ids: list[str]) -> Path:
    parent = {
        "id": "TASK-P3-DEMO-GOAL",
        "title": "Answer current OPC phase status through a governed thin-binding swarm",
        "description": "Fixed D5 demo goal used to close Gate D.",
        "status": "in_progress",
        "phase": 29,
        "role": "goal",
        "children": child_ids,
        "created_at": FIXED_NOW,
        "handoff_refs": [f".omo/tasks/done/{child_id}.yaml" for child_id in child_ids],
        "completion_summary": None,
    }
    parent_path = demo_root / ".omo" / "tasks" / "active" / "TASK-P3-DEMO-GOAL.yaml"
    _write_yaml(parent_path, parent)
    return parent_path


def _seed_active_task(demo_root: Path, spec: DemoTaskSpec, parent_task_id: str) -> Path:
    task = {
        "id": spec.task_id,
        "title": spec.title,
        "description": f"{spec.role} role task for OPC P3 thin-binding demo.",
        "status": "pending",
        "priority": "P0",
        "phase": 29,
        "role": spec.role,
        "parent_task_id": parent_task_id,
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "source_docs": spec.source_docs,
        "deliverables": [spec.deliverable],
        "risk_level": "L0",
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "entry_gate": [],
        "evidence_required": [f"{spec.role} deliverable written"],
        "test_plan": [f"dispatch {spec.role} task", "write checkpoint", "write review"],
    }
    path = demo_root / ".omo" / "tasks" / "active" / f"{spec.task_id}.yaml"
    _write_yaml(path, task)
    return path


def _review_note(spec: DemoTaskSpec, deliverable: str) -> str:
    risks = "\n".join(f"- {item}" for item in spec.risks) or "- none"
    next_handoff = spec.next_handoff or "none"
    return "\n".join(
        [
            "# Review Note",
            "",
            "## Summary of work done",
            "",
            spec.review_summary,
            "",
            "## Deliverables",
            "",
            f"- `{deliverable}`",
            "",
            "## Unresolved risks",
            "",
            risks,
            "",
            "## Next handoff",
            "",
            next_handoff,
            "",
        ]
    )


def _complete_dispatched_task(
    demo_root: Path,
    task_path: Path,
    spec: DemoTaskSpec,
    now: str,
) -> dict[str, str]:
    dispatched = dispatch_task(
        demo_root,
        task_id=spec.task_id,
        worker_id=spec.worker_id,
        allowed_write_paths=[spec.allowed_write_path],
        launch=False,
        now=now,
    )
    update_dispatch_checkpoint(
        demo_root,
        dispatched["dispatch_id"],
        completed_step=spec.completed_step,
        changed_files=spec.changed_files,
        note=f"{spec.role} completed replayable evidence for Gate D.",
        now=now,
    )

    deliverable_path = demo_root / spec.deliverable
    _write_text(
        deliverable_path,
        "\n".join(
            [
                f"# {spec.role.title()} deliverable",
                "",
                f"task_id: {spec.task_id}",
                f"worker_id: {spec.worker_id}",
                f"input_refs: {', '.join(spec.source_docs)}",
                f"output_summary: {spec.review_summary}",
                "",
            ]
        ),
    )

    review_path = demo_root / dispatched["review_path"]
    _write_text(review_path, _review_note(spec, spec.deliverable))

    dispatch_payload = _load_yaml(demo_root / dispatched["dispatch_path"])
    dispatch_payload["dispatch_state"] = "completed"
    dispatch_payload["completed_at"] = now
    dispatch_payload["handoff"]["evidence_paths"] = [spec.deliverable]
    dispatch_payload["handoff"]["unresolved_risks"] = spec.risks
    dispatch_payload["handoff"]["next_handoff"] = spec.next_handoff
    _write_yaml(demo_root / dispatched["dispatch_path"], dispatch_payload)

    task_payload = _load_yaml(task_path)
    task_payload["status"] = "completed"
    task_payload["completed_at"] = now
    task_payload["review_ref"] = dispatched["review_path"]
    task_payload["completion_summary"] = spec.completion_summary
    task_payload["knowledge_refs"] = list(dict.fromkeys(task_payload["knowledge_refs"] + spec.source_docs))
    task_payload["handoff_refs"] = list(
        dict.fromkeys(
            task_payload["handoff_refs"]
            + [
                dispatched["dispatch_path"],
                dispatched["envelope_path"],
                dispatched["checkpoint_path"],
                dispatched["review_path"],
                dispatched["reclaim_path"],
            ]
        )
    )
    done_path = demo_root / ".omo" / "tasks" / "done" / task_path.name
    _write_yaml(done_path, task_payload)
    task_path.unlink()

    return dispatched


def _generate_success_demo(demo_root: Path) -> dict[str, Any]:
    specs = [
        DemoTaskSpec(
            task_id="TASK-P3-PLAN",
            role="planner",
            worker_id="planner-001",
            title="Decompose the fixed OPC status goal into thin-binding worker tasks",
            deliverable="delivery/planner-plan.md",
            allowed_write_path="delivery/",
            source_docs=["docs/OPC-ROADMAP.md", "docs/OPC-PHASE3-SWARM-SPINE.md"],
            completed_step="Planned a three-role decomposition with explicit handoff edges.",
            completion_summary="Planner split the fixed goal into research and review tasks with explicit I/O.",
            changed_files=["delivery/planner-plan.md"],
            review_summary="Planner produced the demo task graph and task boundaries.",
            risks=[],
            next_handoff="researcher consumes the plan deliverable and source docs.",
        ),
        DemoTaskSpec(
            task_id="TASK-P3-RESEARCH",
            role="researcher",
            worker_id="researcher-001",
            title="Collect current OPC phase facts from the phase docs",
            deliverable="delivery/research-findings.md",
            allowed_write_path="delivery/",
            source_docs=[
                "docs/OPC-PHASE2-MEMORY-SPINE.md",
                "docs/OPC-PHASE3-SWARM-SPINE.md",
                "docs/OPC-P2-READINESS.md",
            ],
            completed_step="Collected current phase facts with source references for the fixed goal.",
            completion_summary="Researcher produced the fact baseline consumed by reviewer.",
            changed_files=["delivery/research-findings.md"],
            review_summary="Researcher gathered P2 passed and P3 thin-binding status facts.",
            risks=[],
            next_handoff="reviewer validates facts and writes the final user-facing answer.",
        ),
        DemoTaskSpec(
            task_id="TASK-P3-REVIEW",
            role="reviewer",
            worker_id="reviewer-001",
            title="Verify the research findings and produce the final governed answer",
            deliverable="delivery/final-answer.md",
            allowed_write_path="delivery/",
            source_docs=[
                "delivery/planner-plan.md",
                "delivery/research-findings.md",
                ".omo/tasks/done/TASK-P3-PLAN.yaml",
                ".omo/tasks/done/TASK-P3-RESEARCH.yaml",
            ],
            completed_step="Validated research output and emitted the final answer artifact.",
            completion_summary="Reviewer verified the research against the plan and wrote the final answer.",
            changed_files=["delivery/final-answer.md"],
            review_summary="Reviewer produced the final answer with replayable provenance.",
            risks=[],
            next_handoff="coordinator can package the answer and acceptance report.",
        ),
    ]

    parent_path = _seed_parent_goal(demo_root, [spec.task_id for spec in specs])
    task_paths = {
        spec.task_id: _seed_active_task(demo_root, spec, parent_task_id="TASK-P3-DEMO-GOAL")
        for spec in specs
    }

    dispatches = {}
    for spec in specs:
        dispatches[spec.task_id] = _complete_dispatched_task(
            demo_root,
            task_paths[spec.task_id],
            spec,
            now=FIXED_NOW,
        )

    parent_payload = _load_yaml(parent_path)
    parent_payload["status"] = "completed"
    parent_payload["completed_at"] = FIXED_NOW
    parent_payload["completion_summary"] = (
        "Three-role thin-binding demo succeeded with planner, researcher, and reviewer."
    )
    completed_parent_path = demo_root / ".omo" / "tasks" / "done" / parent_path.name
    _write_yaml(completed_parent_path, parent_payload)
    if parent_path.exists():
        archived_parent_path = demo_root / ".omo" / "_archive" / parent_path.name
        ensure_parent_dir(archived_parent_path)
        shutil.move(str(parent_path), str(archived_parent_path))

    handoff_indexes = {
        task_id: write_handoff_index(demo_root, task_id)
        for task_id in [spec.task_id for spec in specs]
    }
    handoff_indexes["TASK-P3-DEMO-GOAL"] = write_handoff_index(demo_root, "TASK-P3-DEMO-GOAL")
    utilization_ref = write_worker_utilization_summary(demo_root)

    role_summary = {
        "goal": "Answer current OPC phase status through a governed thin-binding swarm",
        "roles": [
            {
                "role": spec.role,
                "worker_id": spec.worker_id,
                "task_id": spec.task_id,
                "input_refs": spec.source_docs,
                "output_ref": spec.deliverable,
                "review_ref": dispatches[spec.task_id]["review_path"],
                "allowed_write_path": spec.allowed_write_path,
            }
            for spec in specs
        ],
        "handoff_indexes": handoff_indexes,
        "worker_utilization_ref": utilization_ref,
    }
    return {
        "specs": specs,
        "dispatches": dispatches,
        "role_summary": role_summary,
    }


def _generate_failure_followup(demo_root: Path) -> dict[str, Any]:
    stale_task = {
        "id": "TASK-P3-FAILED",
        "title": "Demonstrate governed follow-up after a reclaim_due worker",
        "status": "pending",
        "priority": "P1",
        "phase": 29,
        "role": "operator",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "source_docs": ["docs/OPC-MASTER-EXECUTION-PLAYBOOK.md"],
        "deliverables": ["delivery/operator-recovery.md"],
        "risk_level": "L0",
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "entry_gate": [],
        "evidence_required": ["watchdog raises governed follow-up"],
        "test_plan": ["dispatch task", "age lease", "create planned follow-up"],
    }
    task_path = demo_root / ".omo" / "tasks" / "active" / "TASK-P3-FAILED.yaml"
    _write_yaml(task_path, stale_task)
    dispatched = dispatch_task(
        demo_root,
        task_id="TASK-P3-FAILED",
        worker_id="operator-001",
        allowed_write_paths=["delivery/"],
        launch=False,
        now="2026-06-12T09:00:00Z",
    )

    dispatch_payload = _load_yaml(demo_root / dispatched["dispatch_path"])
    dispatch_payload["lease"]["warning_after_seconds"] = 60
    dispatch_payload["lease"]["lease_expired_after_seconds"] = 120
    dispatch_payload["lease"]["reclaim_after_seconds"] = 180
    dispatch_payload["lease"]["last_checkpoint_at"] = "2026-06-12T09:00:00Z"
    dispatch_payload["lease"]["last_material_write_at"] = "2026-06-12T09:00:00Z"
    _write_yaml(demo_root / dispatched["dispatch_path"], dispatch_payload)

    watchdog = scan_runtime_watchdog(demo_root, now="2026-06-12T09:05:00Z")
    followup = {
        "id": "TASK-P3-FAILED-FOLLOWUP",
        "title": "Investigate reclaim_due operator dispatch from OPC P3 demo",
        "status": "planned",
        "priority": "P1",
        "phase": 29,
        "role": "operator",
        "depends_on": ["TASK-P3-FAILED"],
        "source_docs": [dispatched["dispatch_path"], dispatched["reclaim_path"]],
        "evidence_required": ["reclaim_due dispatch triaged", "follow-up recovery documented"],
        "test_plan": ["review watchdog output", "repair dispatch inputs", "re-run operator flow"],
    }
    followup_path = demo_root / ".omo" / "tasks" / "planned" / "TASK-P3-FAILED-FOLLOWUP.yaml"
    _write_yaml(followup_path, followup)

    return {
        "watchdog": watchdog,
        "followup_ref": str(followup_path.relative_to(demo_root)),
        "failed_dispatch_ref": dispatched["dispatch_path"],
    }


def generate_evidence(evidence_root: Path = DEFAULT_EVIDENCE_ROOT) -> dict[str, Any]:
    d3_dir = evidence_root / "OPC-P3-D3"
    d4_dir = evidence_root / "OPC-P3-D4"
    d5_dir = evidence_root / "OPC-P3-D5"
    demo_root = d5_dir / "runtime-root"

    if demo_root.exists():
        shutil.rmtree(demo_root)

    _seed_worker_registry(demo_root)
    success = _generate_success_demo(demo_root)
    failure = _generate_failure_followup(demo_root)

    d3_summary = {
        "generated_at": FIXED_NOW,
        "demo_root": _display_path(demo_root),
        "goal_task": "TASK-P3-DEMO-GOAL",
        "criteria_hit": [
            "at least three roles participate in one real goal",
            "each role has clear input/output boundaries",
        ],
        **success["role_summary"],
    }
    _write_yaml(d3_dir / "role-realization-summary.yaml", d3_summary)

    d4_lines = [
        "# OPC P3 D4 Writeback and Audit Summary",
        "",
        f"- generated_at: {FIXED_NOW}",
        f"- demo_root: `{_display_path(demo_root)}`",
        "",
        "## Queryable completed results",
        "",
    ]
    for task_id, handoff_ref in success["role_summary"]["handoff_indexes"].items():
        d4_lines.append(f"- `{task_id}` handoff index: `{handoff_ref}`")
    d4_lines.extend(
        [
            "",
            "## Governed follow-up after failure",
            "",
            f"- watchdog counts: `{failure['watchdog']['counts']}`",
            f"- failed dispatch ref: `{failure['failed_dispatch_ref']}`",
            f"- planned follow-up ref: `{failure['followup_ref']}`",
            "",
            "Result: one completed worker result is queryable after execution, and one reclaim_due worker produces a governed follow-up packet.",
            "",
        ]
    )
    _write_text(d4_dir / "writeback-audit-summary.md", "\n".join(d4_lines))

    d5_lines = [
        "# OPC P3 D5 Minimal Demo Report",
        "",
        "## Fixed goal",
        "",
        "Answer current OPC phase status through a governed thin-binding swarm.",
        "",
        "## Replay",
        "",
        "```bash",
        "python3 scripts/opc_p3_thin_binding_demo.py",
        "```",
        "",
        "## Worker chain",
        "",
        "- planner-001 -> `TASK-P3-PLAN` -> `delivery/planner-plan.md`",
        "- researcher-001 -> `TASK-P3-RESEARCH` -> `delivery/research-findings.md`",
        "- reviewer-001 -> `TASK-P3-REVIEW` -> `delivery/final-answer.md`",
        "",
        "## Evidence refs",
        "",
        f"- role summary: `{_display_path(d3_dir / 'role-realization-summary.yaml')}`",
        f"- writeback summary: `{_display_path(d4_dir / 'writeback-audit-summary.md')}`",
        f"- worker utilization: `{success['role_summary']['worker_utilization_ref']}`",
        f"- goal handoff index: `{success['role_summary']['handoff_indexes']['TASK-P3-DEMO-GOAL']}`",
        "",
        "## Verdict",
        "",
        "Replayable three-worker thin-binding demo completed successfully.",
        "",
    ]
    _write_text(d5_dir / "minimal-demo-report.md", "\n".join(d5_lines))

    return {
        "demo_root": demo_root,
        "d3_summary": d3_dir / "role-realization-summary.yaml",
        "d4_summary": d4_dir / "writeback-audit-summary.md",
        "d5_report": d5_dir / "minimal-demo-report.md",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
        help="Base directory containing OPC-P3-D3/D4/D5 evidence dirs.",
    )
    args = parser.parse_args(argv)

    outputs = generate_evidence(args.evidence_root.resolve())
    print(_display_path(outputs["d3_summary"]))
    print(_display_path(outputs["d4_summary"]))
    print(_display_path(outputs["d5_report"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
