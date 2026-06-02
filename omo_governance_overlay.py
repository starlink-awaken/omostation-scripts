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


def build_governance_overlay_status(root: Path, *, omo_dir: str | Path = ".omo", now: str) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    state = _load_yaml_required(root / omo_ref / "_control" / "governance-overlay" / "current.yaml")
    roadmap = _load_yaml_required(root / omo_ref / "_truth" / "governance-overlay" / "roadmap.yaml")
    policy = _load_yaml_required(root / omo_ref / "_truth" / "governance-overlay" / "autopilot-policy.yaml")

    completed_items = {item["id"] for item in roadmap.get("items", []) if item.get("status") == "done"}
    autopilot_candidates: list[dict[str, object]] = []
    blocked_items: list[dict[str, object]] = []

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
    if autopilot_candidates:
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
