#!/usr/bin/env python3
"""OPC P5 technical-radar runner with durable trigger history.

目的:
  - 为 P5-F1 提供手动/cron 共用入口
  - 每次运行都写 scenario receipt + 历史索引
  - 区分 trigger_source=manual/cron, 为后续真实时间窗验收留痕
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lib.bootstrap import workspace_root, omo_src_path

ROOT = workspace_root()
sys.path.insert(0, str(omo_src_path()))

from omo.omo_radar_history import (
    classify_candidate as _classify_candidate_runtime,
    load_radar_history as _load_history_runtime,
    update_radar_history as _update_history_runtime,
    write_radar_snapshot as _write_daily_snapshot_runtime,
)
from omo.omo_weekly_loop import write_mof_state_bridge_snapshot


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _history_path() -> Path:
    return ROOT / ".omo" / "_control" / "evolution" / "radar-history.json"


def _day_bucket() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _trigger_source() -> str:
    return os.environ.get("OPC_TRIGGER", "manual")


def _run_radar(limit: int = 8) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "projects" / "cockpit" / "src"))
    from cockpit.commands.scenario import _archive_scenario_receipt, _f1_technical_radar  # type: ignore

    payload = _f1_technical_radar(limit=limit)
    payload["trigger_source"] = _trigger_source()
    payload["archive_path"] = _archive_scenario_receipt(payload)
    return payload


def _classify_candidate(candidate: dict[str, Any]) -> bool:
    return _classify_candidate_runtime(candidate)


def _load_history() -> dict[str, Any]:
    return _load_history_runtime(ROOT)


def _update_history(payload: dict[str, Any]) -> dict[str, Any]:
    return _update_history_runtime(ROOT, payload)


def _write_daily_snapshot(payload: dict[str, Any], history: dict[str, Any]) -> Path:
    return _write_daily_snapshot_runtime(ROOT, payload, history)


def main() -> int:
    payload = _run_radar()
    history = _update_history(payload)
    snapshot_path = _write_daily_snapshot(payload, history)
    print(f"# trigger: {payload['trigger_source']}", file=sys.stderr)
    print(f"# history: {str(_history_path().relative_to(ROOT))}", file=sys.stderr)
    print(f"# snapshot: {str(snapshot_path.relative_to(ROOT))}", file=sys.stderr)
    print(json.dumps({"payload": payload, "history": history.get("summary", {})}, ensure_ascii=False, indent=2))
    # P5 增强 (2026-06-14): cron wrapper 末尾跑 mof-state-bridge --strict
    # 失同步写 .omo/_delivery/audit-rollout/{date}-mof-state-bridge.json
    _run_mof_state_bridge_cron()
    # P5 增强 (2026-06-25): 证据驱动 smoke + God Module 检测 (让运行现实进入度量闭环)
    _run_evidence_smoke_cron()
    return 0


def _run_mof_state_bridge_cron() -> None:
    """P5 增强: cron 跑完后跑 mof-state-bridge --strict 写 5repos 兼容字段."""
    import subprocess
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = subprocess.run(
        ["python3", "projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py",
         "--json", "--strict"],
        cwd=str(ROOT),
        capture_output=True, text=True, timeout=60,
    )
    in_sync = False
    m1_count = omo_count = paired = drift = m1_only = 0
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout.strip())
            diff = data.get("diff", {})
            m1_count = data.get("m1_count", 0)
            omo_count = data.get("omo_count", 0)
            paired = data.get("paired", 0)
            drift = len(diff.get("drifts", []))
            m1_only = len(diff.get("m1_only", []))
            in_sync = m1_only == 0
        except json.JSONDecodeError:
            pass
    payload = {
        "generated_at": stamp,
        "trigger_source": os.environ.get("OPC_TRIGGER", "manual"),
        "mode": os.environ.get("OPC_MODE", "weekly"),
        "source": "opc_p5_radar_cron",
        "mof_state_bridge": {
            "in_sync": in_sync,
            "m1_count": m1_count,
            "omo_count": omo_count,
            "paired": paired,
            "drift_count": drift,
            "m1_only": m1_only,
            "blocking": not in_sync,
        },
    }
    write_mof_state_bridge_snapshot(ROOT, payload)
    if not in_sync:
        print(f"⚠️  mof-state-bridge 失同步: {m1_only} M1 only, written to 5repos", file=sys.stderr)


def _run_evidence_smoke_cron() -> None:
    """P5 增强 (2026-06-25): 证据驱动 smoke + God Module 检测, 让运行现实进入度量闭环.

    Meadows 层 8 (反馈回路): evidence_health_score + God Module 数写进 delivery,
    让 dashboard/radar 能读到运行现实 (而非只有任务治理分).
    """
    import subprocess

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir = ROOT / ".omo" / "_delivery" / "evidence-smoke"
    out_dir.mkdir(parents=True, exist_ok=True)

    # evidence-smoke (拿 evidence_health_score)
    evidence_score = None
    try:
        result = subprocess.run(
            ["python3", str(ROOT / "bin" / "evidence-smoke.py"), "--quiet"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode == 0 and result.stdout.strip():
            evidence_score = float(result.stdout.strip())
    except Exception:
        pass

    # check-god-module (JSON, 落盘供 dashboard)
    god_total = None
    try:
        result = subprocess.run(
            ["python3", str(ROOT / "bin" / "check-god-module.py"), "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            god_total = data.get("total")
            (out_dir / "god-module.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except Exception:
        pass

    summary = {
        "generated_at": stamp,
        "trigger_source": os.environ.get("OPC_TRIGGER", "manual"),
        "source": "opc_p5_radar_cron",
        "evidence_health_score": evidence_score,
        "god_module_total": god_total,
    }
    (out_dir / "cron-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"# evidence-smoke: score={evidence_score}, god-module total={god_total}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
