from __future__ import annotations

from pathlib import Path

import yaml


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _item_sort_key(item: dict[str, object]) -> tuple[int, str]:
    return (0 if item["priority"] == "P0" else 1, str(item["id"]))


def _missing_target_refs(root: Path, refs: list[str]) -> list[str]:
    return [ref for ref in refs if not (root / ref).exists()]


def _load_optional_yaml(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _dispatch_payload(root: Path, run_ref: str | None) -> dict[str, object] | None:
    if not run_ref:
        return None
    return _load_optional_yaml(root / run_ref)


def _derived_allowed_write_paths(task: dict[str, object]) -> list[str]:
    paths: list[str] = []
    for deliverable in task.get("deliverables", []):
        path = str(deliverable)
        if path.endswith("/"):
            candidate = path
        else:
            candidate = str(Path(path).parent)
            if candidate == ".":
                candidate = path
            elif not candidate.endswith("/"):
                candidate = f"{candidate}/"
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _launch_contract_state(task: dict[str, object], dispatch: dict[str, object] | None) -> tuple[str, str]:
    deliverables = list(task.get("deliverables", []))
    allowed_paths = _derived_allowed_write_paths(task)
    if not deliverables or not allowed_paths:
        return ("contract_gap", "dispatch exists but task has no launch-ready write scope")
    if dispatch and dispatch.get("dispatch_state") == "dispatched":
        return ("dispatch_only", "dispatch exists and task is ready for launch")
    return ("launch_ready", "task has explicit launch-ready write scope")


def _target_state(root: Path, target_ref: str, *, omo_dir: str | Path = ".omo") -> dict[str, object]:
    if not target_ref.startswith(".omo/tasks/planned/"):
        return {
            "target_ref": target_ref,
            "task_id": None,
            "state": "unsupported_target_ref",
            "detail": "only .omo/tasks/planned/*.yaml target refs are supported in v1",
        }

    omo_ref = Path(omo_dir)
    filename = Path(target_ref).name
    directories = [
        ("done", "done"),
        ("blocked", "planned_blocked"),
        ("active", None),
        ("planned", "planned_pending"),
    ]
    for directory, fixed_state in directories:
        task_path = root / omo_ref / "tasks" / directory / filename
        if not task_path.exists():
            continue
        task = _load_yaml_required(task_path)
        task_id = task.get("id")
        if fixed_state:
            return {
                "target_ref": target_ref,
                "task_id": task_id,
                "state": fixed_state,
                "detail": f"task currently exists in tasks/{directory}/",
            }
        status = str(task.get("status", "pending"))
        dispatch = _dispatch_payload(root, str(task.get("run_ref")) if task.get("run_ref") else None)
        if status == "in_progress" and dispatch:
            contract_state, detail = _launch_contract_state(task, dispatch)
            dispatch_state = str(dispatch.get("dispatch_state"))
            if dispatch_state == "dispatched" and contract_state == "contract_gap":
                return {
                    "target_ref": target_ref,
                    "task_id": task_id,
                    "state": "active_dispatch_blocked",
                    "detail": detail,
                }
            if dispatch_state == "dispatched":
                return {
                    "target_ref": target_ref,
                    "task_id": task_id,
                    "state": "active_dispatched",
                    "detail": detail,
                }
        active_state = {
            "pending": "active_pending",
            "in_progress": "active_in_progress",
            "review": "active_review",
        }.get(status, "active_in_progress")
        return {
            "target_ref": target_ref,
            "task_id": task_id,
            "state": active_state,
            "detail": f"task currently exists in tasks/active/ with status {status}",
        }

    return {
        "target_ref": target_ref,
        "task_id": Path(target_ref).stem,
        "state": "missing_target_ref",
        "detail": "target ref is missing from planned/active/done/blocked task directories",
    }


def build_governance_overlay_status(root: Path, *, omo_dir: str | Path = ".omo", now: str) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    state = _load_yaml_required(root / omo_ref / "_control" / "governance-overlay" / "current.yaml")
    roadmap = _load_yaml_required(root / omo_ref / "_truth" / "governance-overlay" / "roadmap.yaml")
    policy = _load_yaml_required(root / omo_ref / "_truth" / "governance-overlay" / "autopilot-policy.yaml")

    completed_items = {item["id"] for item in roadmap.get("items", []) if item.get("status") == "done"}
    autopilot_candidates: list[dict[str, object]] = []
    blocked_items: list[dict[str, object]] = []
    active_items = [item for item in roadmap.get("items", []) if item.get("status") == "in_progress"]
    if len(active_items) > 1:
        raise ValueError("multiple in_progress roadmap items are not supported in v1")
    active_item = active_items[0] if active_items else None
    active_target_states = (
        [_target_state(root, str(ref), omo_dir=omo_dir) for ref in active_item.get("target_refs", [])] if active_item else []
    )

    for item in sorted(roadmap.get("items", []), key=_item_sort_key):
        item_status = str(item.get("status", "pending"))
        if item_status == "done":
            continue
        if item_status == "blocked":
            blocked_items.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "reason": str(item.get("blocked_reason", "blocked")),
                }
            )
            continue
        if item_status != "pending":
            continue
        missing_refs = _missing_target_refs(root, list(item.get("target_refs", [])))
        unmet_deps = [dep for dep in item.get("depends_on", []) if dep not in completed_items]
        if missing_refs:
            blocked_items.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "reason": "missing_target_refs",
                    "missing_target_refs": missing_refs,
                }
            )
            continue
        if unmet_deps:
            blocked_items.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "reason": "unmet_dependencies",
                    "depends_on": unmet_deps,
                }
            )
            continue

        autopilot_candidates.append(
            {
                "id": item["id"],
                "title": item["title"],
                "type": item["type"],
                "priority": item["priority"],
                "target_refs": item.get("target_refs", []),
            }
        )

    next_action = "idle"
    if active_item:
        if any(target["state"] == "active_pending" for target in active_target_states):
            first_pending = next(target for target in active_target_states if target["state"] == "active_pending")
            next_action = f"dispatch:{first_pending['task_id']}"
        elif any(target["state"] == "active_dispatch_blocked" for target in active_target_states):
            blocked = next(target for target in active_target_states if target["state"] == "active_dispatch_blocked")
            next_action = f"contract:{blocked['task_id']}"
        elif any(target["state"] == "active_dispatched" for target in active_target_states):
            dispatched = next(target for target in active_target_states if target["state"] == "active_dispatched")
            next_action = f"launch:{dispatched['task_id']}"
        elif any(target["state"] == "active_review" for target in active_target_states):
            first_review = next(target for target in active_target_states if target["state"] == "active_review")
            next_action = f"verify:{first_review['task_id']}"
        elif any(target["state"] in {"active_in_progress", "active_review"} for target in active_target_states):
            next_action = f"monitor:{active_item['id']}"
        elif any(target["state"] == "planned_pending" for target in active_target_states):
            next_action = f"advance:{active_item['id']}"
        elif active_target_states and all(target["state"] == "done" for target in active_target_states):
            next_action = f"close:{active_item['id']}"
        elif active_target_states and all(
            target["state"] in {"planned_blocked", "unsupported_target_ref", "missing_target_ref"}
            for target in active_target_states
        ):
            next_action = f"block:{active_item['id']}"
    elif autopilot_candidates:
        next_action = f"advance:{autopilot_candidates[0]['id']}"
    elif any(item["reason"] == "missing_target_refs" for item in blocked_items):
        next_action = "repair_refs"

    yaml_packet = {
        "overlay_id": state["overlay_id"],
        "generated_at": now,
        "status": state["status"],
        "autopilot_mode": state["autopilot_mode"],
        "intake_scope": state["intake_scope"],
        "current_milestone": state["current_milestone"],
        "next_milestone": state["next_milestone"],
        "success_target": state["success_target"],
        "eligible_count": len(autopilot_candidates),
        "blocked_count": len(blocked_items),
        "active_roadmap_item": (
            {
                "id": active_item["id"],
                "title": active_item["title"],
                "type": active_item["type"],
                "priority": active_item["priority"],
            }
            if active_item
            else None
        ),
        "active_target_states": active_target_states,
        "autopilot_candidates": autopilot_candidates,
        "blocked_items": blocked_items,
        "next_action": next_action,
        "policy": policy,
    }
    markdown_lines = [
        "# Governance Overlay Status",
        "",
        f"Overlay: {yaml_packet['overlay_id']}",
        f"Generated at: {now}",
        f"Current milestone: {yaml_packet['current_milestone']}",
        f"Next milestone: {yaml_packet['next_milestone'] or 'none'}",
        f"Eligible items: {yaml_packet['eligible_count']}",
        f"Blocked items: {yaml_packet['blocked_count']}",
        f"Next action: {yaml_packet['next_action']}",
    ]
    if active_item:
        markdown_lines.extend(
            [
                "",
                f"## Active roadmap item: {active_item['id']}",
                "",
                f"title={active_item['title']}",
                f"priority={active_item['priority']}",
            ]
        )
        for target in active_target_states:
            markdown_lines.extend(
                [
                    "",
                    f"target_ref={target['target_ref']}",
                    f"task_id={target['task_id']}",
                    f"state={target['state']}",
                ]
            )
    for item in autopilot_candidates:
        markdown_lines.extend(
            [
                "",
                f"## Candidate: {item['id']}",
                "",
                f"title={item['title']}",
                f"priority={item['priority']}",
                f"type={item['type']}",
            ]
        )
    for item in blocked_items:
        markdown_lines.extend(
            [
                "",
                f"## Blocked: {item['id']}",
                "",
                f"title={item['title']}",
                f"reason={item['reason']}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
