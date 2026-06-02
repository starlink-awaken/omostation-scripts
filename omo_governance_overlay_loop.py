from __future__ import annotations

from pathlib import Path

import yaml

try:
    from scripts.omo_governance_overlay import build_governance_overlay_status
    from scripts.omo_promotion_approval import evaluate_promotion_approval
except ModuleNotFoundError:
    from omo_governance_overlay import build_governance_overlay_status
    from omo_promotion_approval import evaluate_promotion_approval


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _roadmap_item(roadmap: dict, roadmap_item_id: str) -> dict:
    for item in roadmap.get("items", []):
        if item.get("id") == roadmap_item_id:
            return item
    raise KeyError(f"unknown roadmap item: {roadmap_item_id}")


def _task_has_task_specific_promotion_approval(approval_ref: str | None) -> bool:
    return bool(approval_ref and approval_ref.endswith(".yaml") and "-promotion-approval-" in approval_ref)


def _target_action(root: Path, target_ref: str) -> dict[str, object]:
    if not target_ref.startswith(".omo/tasks/planned/"):
        return {
            "target_ref": target_ref,
            "task_id": None,
            "action": "mark_blocked",
            "result": "unsupported_target_ref",
            "detail": "only .omo/tasks/planned/*.yaml target refs are supported in v1",
        }

    task = _load_yaml_required(root / target_ref)
    task_id = str(task["id"])
    if task.get("human_approval_required"):
        approval_ref = task.get("approval_ref")
        approval_eval = evaluate_promotion_approval(
            root,
            approval_ref=approval_ref,
            task_id=task_id,
            task_ref=target_ref,
        )
        if approval_eval["approval_ready"]:
            return {
                "target_ref": target_ref,
                "task_id": task_id,
                "action": "promote_apply",
                "result": "promotion_ready",
                "detail": "task-specific promotion approval is already granted",
            }
        if _task_has_task_specific_promotion_approval(str(approval_ref) if approval_ref else None):
            return {
                "target_ref": target_ref,
                "task_id": task_id,
                "action": "await_approval",
                "result": "approval_pending",
                "detail": "task-specific promotion approval exists but is not granted yet",
            }
        return {
            "target_ref": target_ref,
            "task_id": task_id,
            "action": "request_approval",
            "result": "approval_request_needed",
            "detail": "task requires task-specific promotion approval before promote-apply",
        }

    return {
        "target_ref": target_ref,
        "task_id": task_id,
        "action": "promote_apply",
        "result": "promotion_ready",
        "detail": "task is eligible for promote-apply without human approval",
    }


def plan_governance_overlay_cycle(root: Path, *, omo_dir: str | Path = ".omo", actor: str, now: str) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    roadmap = _load_yaml_required(root / omo_ref / "_truth" / "governance-overlay" / "roadmap.yaml")
    status = build_governance_overlay_status(root, omo_dir=omo_dir, now=now)["yaml"]
    run = {
        "run_id": f"governance-overlay-{now.replace(':', '-')}",
        "overlay_id": status["overlay_id"],
        "actor": actor,
        "started_at": now,
        "completed_at": now,
        "next_action_before_run": status["next_action"],
        "roadmap_item_id": None,
        "summary": "idle",
        "target_results": [],
    }
    if not status["autopilot_candidates"]:
        return {"run": run, "roadmap": roadmap, "mutated": False}

    roadmap_item_id = str(status["autopilot_candidates"][0]["id"])
    item = _roadmap_item(roadmap, roadmap_item_id)
    run["roadmap_item_id"] = roadmap_item_id
    run["target_results"] = [_target_action(root, str(ref)) for ref in item.get("target_refs", [])]
    if run["target_results"] and all(result["result"] == "unsupported_target_ref" for result in run["target_results"]):
        run["summary"] = "blocked"
    else:
        run["summary"] = "advanced"
    return {"run": run, "roadmap": roadmap, "mutated": False}
