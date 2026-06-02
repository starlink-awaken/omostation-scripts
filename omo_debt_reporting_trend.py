from __future__ import annotations

try:
    from scripts.omo_debt_reporting_history import _validate_run_stamp
except ModuleNotFoundError:
    from omo_debt_reporting_history import _validate_run_stamp


def _trend_run(entry: dict[str, object]) -> dict[str, object]:
    if not entry["reporting_exists"] or any(
        entry[field] is None
        for field in (
            "total_items",
            "executed_item_count",
            "approval_coverage_rate",
            "execution_completion_rate",
        )
    ):
        raise ValueError(f"missing reporting trend metadata for run: {entry['run_stamp']}")
    return {
        "run_stamp": entry["run_stamp"],
        "dispatch_run_ref": entry["dispatch_run_ref"],
        "reporting_ref": entry["reporting_ref"],
        "total_items": entry["total_items"],
        "executed_item_count": entry["executed_item_count"],
        "approval_coverage_rate": entry["approval_coverage_rate"],
        "execution_completion_rate": entry["execution_completion_rate"],
    }


def _interval(previous: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    return {
        "from_run_stamp": previous["run_stamp"],
        "to_run_stamp": current["run_stamp"],
        "total_items_delta": current["total_items"] - previous["total_items"],
        "executed_item_count_delta": current["executed_item_count"] - previous["executed_item_count"],
        "approval_coverage_rate_delta": current["approval_coverage_rate"] - previous["approval_coverage_rate"],
        "execution_completion_rate_delta": current["execution_completion_rate"] - previous["execution_completion_rate"],
    }


def _run_index(runs: list[dict[str, object]], run_stamp: str, *, label: str) -> int:
    for index, entry in enumerate(runs):
        if entry["run_stamp"] == run_stamp:
            return index
    raise ValueError(f"{label} not in history: {run_stamp}")


def _select_runs(
    history_packet: dict[str, object],
    *,
    window_requested: int | None,
    from_run_stamp_requested: str | None,
    to_run_stamp_requested: str | None,
) -> list[dict[str, object]]:
    runs = history_packet["runs"]
    if from_run_stamp_requested is not None or to_run_stamp_requested is not None:
        if from_run_stamp_requested is None or to_run_stamp_requested is None:
            raise ValueError("range mode requires both from-run-stamp and to-run-stamp")
        try:
            _validate_run_stamp(from_run_stamp_requested)
        except ValueError as exc:
            raise ValueError(f"invalid from-run-stamp: {from_run_stamp_requested}") from exc
        try:
            _validate_run_stamp(to_run_stamp_requested)
        except ValueError as exc:
            raise ValueError(f"invalid to-run-stamp: {to_run_stamp_requested}") from exc
        to_index = _run_index(runs, to_run_stamp_requested, label="to-run-stamp")
        from_index = _run_index(runs, from_run_stamp_requested, label="from-run-stamp")
        if from_index < to_index:
            raise ValueError("from-run-stamp must not be newer than to-run-stamp")
        return runs[to_index : from_index + 1]
    if window_requested is not None:
        return runs[:window_requested]
    return runs


def build_reporting_trend_packet(
    *,
    generated_at: str,
    history_packet: dict[str, object],
    window_requested: int | None = None,
    from_run_stamp_requested: str | None = None,
    to_run_stamp_requested: str | None = None,
) -> dict[str, object]:
    selected_runs = _select_runs(
        history_packet,
        window_requested=window_requested,
        from_run_stamp_requested=from_run_stamp_requested,
        to_run_stamp_requested=to_run_stamp_requested,
    )
    ordered_runs = [_trend_run(entry) for entry in reversed(selected_runs)]
    intervals = [
        _interval(ordered_runs[index], ordered_runs[index + 1])
        for index in range(len(ordered_runs) - 1)
    ]
    oldest_run_stamp = ordered_runs[0]["run_stamp"] if ordered_runs else None
    latest_run_stamp = ordered_runs[-1]["run_stamp"] if ordered_runs else None
    return {
        "generated_at": generated_at,
        "trend_status": "trend_available" if len(ordered_runs) >= 2 else "insufficient_history",
        "window_requested": window_requested,
        "from_run_stamp_requested": from_run_stamp_requested,
        "to_run_stamp_requested": to_run_stamp_requested,
        "window_run_count": len(ordered_runs),
        "oldest_run_stamp": oldest_run_stamp,
        "latest_run_stamp": latest_run_stamp,
        "runs": ordered_runs,
        "intervals": intervals,
    }


def render_reporting_trend_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Reporting Trend",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Trend status: {packet['trend_status']}",
        f"Oldest run: {packet['oldest_run_stamp'] or 'none'}",
        f"Latest run: {packet['latest_run_stamp'] or 'none'}",
        "",
    ]
    if packet["trend_status"] == "insufficient_history":
        lines.extend(["Trend baseline not established yet.", ""])
    for run in packet["runs"]:
        lines.extend(
            [
                f"## Run: {run['run_stamp']}",
                "",
                f"total_items={run['total_items']}",
                f"executed_item_count={run['executed_item_count']}",
                f"approval_coverage_rate={run['approval_coverage_rate']}",
                f"execution_completion_rate={run['execution_completion_rate']}",
                "",
            ]
        )
    for interval in packet["intervals"]:
        lines.extend(
            [
                f"## Interval: {interval['from_run_stamp']} -> {interval['to_run_stamp']}",
                "",
                f"total_items_delta={interval['total_items_delta']}",
                f"executed_item_count_delta={interval['executed_item_count_delta']}",
                f"approval_coverage_rate_delta={interval['approval_coverage_rate_delta']}",
                f"execution_completion_rate_delta={interval['execution_completion_rate_delta']}",
                "",
            ]
        )
    return "\n".join(lines)
