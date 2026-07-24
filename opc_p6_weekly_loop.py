#!/usr/bin/env python3
"""OPC P6 weekly loop runner — 6 阶段流水线.

P6-G1: 6-stage loop radar → gap → task → swarm → audit → retro.
P6-G2: ≥2 周连续周报, 每份 ≥3 candidates + score 排序 + source + timestamp + next-action + 人工审批栏.
P6-G4: ≥1 candidate 从 radar 跑到 retrospective 闭环实证.

输出: runtime/omo/_control/evolution/loop/{week}.json (1 周 1 份)
       runtime/omo/tasks/registry/done/OPC-P6-G1/weekly-{week}.md (markdown 报告)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.bootstrap import setup_omo_src, workspace_root

ROOT = workspace_root()
setup_omo_src()

from omo.omo_weekly_loop import (
    call_drift as _call_drift_runtime,
)
from omo.omo_weekly_loop import (
    call_radar as _call_radar_runtime,
)
from omo.omo_weekly_loop import (
    consecutive_weeks as _consecutive_weeks_runtime,
)
from omo.omo_weekly_loop import (
    load_loop_history as _load_loop_history_runtime,
)
from omo.omo_weekly_loop import (
    run_mof_state_bridge_cron_snapshot,
    run_weekly_loop,
    write_weekly_evidence,
)
from omo.omo_weekly_loop import (
    stage_audit as _stage_audit_runtime,
)
from omo.omo_weekly_loop import (
    stage_gap as _stage_gap_runtime,
)
from omo.omo_weekly_loop import (
    stage_retro as _stage_retro_runtime,
)
from omo.omo_weekly_loop import (
    stage_swarm as _stage_swarm_runtime,
)
from omo.omo_weekly_loop import (
    stage_task as _stage_task_runtime,
)
from omo.omo_weekly_loop import (
    update_loop_history as _update_loop_history_runtime,
)
from omo.omo_weekly_loop import (
    utc_now_iso as _now_iso_runtime,
)
from omo.omo_weekly_loop import (
    week_id as _week_id_runtime,
)


def _now_iso() -> str:
    return _now_iso_runtime()


def _week_id(date: datetime | None = None) -> str:
    return _week_id_runtime(date)


def _load_loop_history() -> dict[str, Any]:
    return _load_loop_history_runtime(ROOT)


def _week_sort_key(week: str) -> tuple[int, int]:
    year, week_num = week.split("-W", 1)
    return int(year), int(week_num)


def _consecutive_weeks(runs: list[dict[str, Any]]) -> int:
    return _consecutive_weeks_runtime(runs)


def _update_loop_history(payload: dict[str, Any]) -> dict[str, Any]:
    return _update_loop_history_runtime(ROOT, payload)


def _call_radar() -> dict[str, Any]:
    return _call_radar_runtime(ROOT)


def _call_drift() -> dict[str, Any]:
    return _call_drift_runtime(ROOT, now_iso=_now_iso())


def _stage_radar() -> dict[str, Any]:
    return {"stage": "radar", "ts": _now_iso(), "output": _call_radar()}


def _stage_gap(radar: dict[str, Any], drift: dict[str, Any]) -> dict[str, Any]:
    return _stage_gap_runtime(radar, drift, now_iso=_now_iso())


def _stage_task(gap: dict[str, Any]) -> dict[str, Any]:
    return _stage_task_runtime(gap, week=_week_id(), now_iso=_now_iso())


def _stage_swarm(task: dict[str, Any]) -> dict[str, Any]:
    return _stage_swarm_runtime(task, now_iso=_now_iso())


def _stage_audit() -> dict[str, Any]:
    return _stage_audit_runtime(ROOT, now_iso=_now_iso())


def _stage_retro(loop_payload: dict[str, Any]) -> dict[str, Any]:
    return _stage_retro_runtime(loop_payload, now_iso=_now_iso())


def run_one_week(week: str | None = None) -> dict[str, Any]:
    stamp = _now_iso()
    return run_weekly_loop(
        ROOT,
        week=week,
        now_iso=stamp,
        radar_fn=_call_radar,
        drift_fn=_call_drift,
    )


def write_evidence(week: str, payload: dict[str, Any]) -> Path:
    """落盘 evidence: JSON + markdown."""
    md_path, _json_path = write_weekly_evidence(ROOT, week, payload)
    return md_path


def main() -> int:
    week = os.environ.get("OPC_WEEK")
    payload = run_one_week(week=week)
    md_path = write_evidence(payload["week"], payload)
    print(f"# week: {payload['week']}", file=sys.stderr)
    print(f"# evidence: {md_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"# json: runtime/omo/_control/evolution/loop/{payload['week']}.json", file=sys.stderr)
    # P6 增强 (2026-06-14): weekly loop 末尾跑 mof-state-bridge --strict
    _run_mof_state_bridge_cron()
    return 0


def _run_mof_state_bridge_cron() -> None:
    """P6 增强: weekly loop 跑完后跑 mof-state-bridge --strict 写 5repos 兼容字段."""
    snapshot = run_mof_state_bridge_cron_snapshot(ROOT)
    payload_out = json.loads(snapshot.read_text(encoding="utf-8"))
    if not payload_out.get("mof_state_bridge", {}).get("in_sync", False):
        m1_only = payload_out.get("mof_state_bridge", {}).get("m1_only", 0)
        print(f"⚠️  mof-state-bridge 失同步: {m1_only} M1 only, written to 5repos", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
