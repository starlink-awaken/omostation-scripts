from __future__ import annotations


def _delta_metric(latest: int | float, prior: int | float | None) -> dict[str, int | float | None]:
    if prior is None:
        return {"latest": latest, "prior": None, "delta": None}
    return {"latest": latest, "prior": prior, "delta": latest - prior}


def _summary_diff(latest_summary: dict[str, object], prior_summary: dict[str, object] | None) -> dict[str, object]:
    prior_state_counts = prior_summary["state_counts"] if prior_summary else None
    return {
        "total_items": _delta_metric(int(latest_summary["total_items"]), int(prior_summary["total_items"]) if prior_summary else None),
        "state_counts": {
            "pending_approval": _delta_metric(
                int(latest_summary["state_counts"]["pending_approval"]),
                int(prior_state_counts["pending_approval"]) if prior_state_counts else None,
            ),
            "ready_to_execute": _delta_metric(
                int(latest_summary["state_counts"]["ready_to_execute"]),
                int(prior_state_counts["ready_to_execute"]) if prior_state_counts else None,
            ),
            "executed": _delta_metric(
                int(latest_summary["state_counts"]["executed"]),
                int(prior_state_counts["executed"]) if prior_state_counts else None,
            ),
        },
        "gate_item_count": _delta_metric(
            int(latest_summary["gate_item_count"]),
            int(prior_summary["gate_item_count"]) if prior_summary else None,
        ),
        "approved_gate_item_count": _delta_metric(
            int(latest_summary["approved_gate_item_count"]),
            int(prior_summary["approved_gate_item_count"]) if prior_summary else None,
        ),
        "approval_coverage_rate": _delta_metric(
            float(latest_summary["approval_coverage_rate"]),
            float(prior_summary["approval_coverage_rate"]) if prior_summary else None,
        ),
        "executed_item_count": _delta_metric(
            int(latest_summary["executed_item_count"]),
            int(prior_summary["executed_item_count"]) if prior_summary else None,
        ),
        "execution_completion_rate": _delta_metric(
            float(latest_summary["execution_completion_rate"]),
            float(prior_summary["execution_completion_rate"]) if prior_summary else None,
        ),
    }


def build_reporting_diff_packet(
    *,
    generated_at: str,
    latest_packet: dict[str, object],
    prior_packet: dict[str, object] | None,
) -> dict[str, object]:
    latest_summary = latest_packet["summary"]
    prior_summary = prior_packet["summary"] if prior_packet else None
    return {
        "generated_at": generated_at,
        "diff_status": "diff_available" if prior_packet else "no_prior_run",
        "latest_run_stamp": latest_packet["run_stamp"],
        "prior_run_stamp": prior_packet["run_stamp"] if prior_packet else None,
        "latest_dispatch_run_ref": latest_packet["dispatch_run_ref"],
        "prior_dispatch_run_ref": prior_packet["dispatch_run_ref"] if prior_packet else None,
        "summary_diff": _summary_diff(latest_summary, prior_summary),
        "owners": None,
    }


def render_reporting_diff_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Reporting Diff",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Diff status: {packet['diff_status']}",
        f"Latest run: {packet['latest_run_stamp']}",
        f"Prior run: {packet['prior_run_stamp'] or 'none'}",
        "",
    ]
    if packet["diff_status"] == "no_prior_run":
        lines.extend(["Prior baseline not established yet.", ""])
    for field, payload in packet["summary_diff"].items():
        if field == "state_counts":
            lines.append("## state_counts")
            lines.append("")
            for state_name, state_payload in payload.items():
                lines.append(
                    f"{state_name}: latest={state_payload['latest']}, prior={state_payload['prior']}, delta={state_payload['delta']}"
                )
            lines.append("")
            continue
        lines.append(f"{field}: latest={payload['latest']}, prior={payload['prior']}, delta={payload['delta']}")
    return "\n".join(lines)
