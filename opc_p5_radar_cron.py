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


ROOT = Path(__file__).resolve().parents[1]


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
    source = str(candidate.get("source", ""))
    return "(DB unavailable)" not in source and candidate.get("evidence_id") is not None


def _load_history() -> dict[str, Any]:
    path = _history_path()
    if not path.exists():
        return {"runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": []}


def _update_history(payload: dict[str, Any]) -> dict[str, Any]:
    history = _load_history()
    runs = history.setdefault("runs", [])
    candidates = payload.get("candidates", [])
    runs.append(
        {
            "generated_at": payload["generated_at"],
            "day": _day_bucket(),
            "trigger_source": payload.get("trigger_source"),
            "candidate_count": payload.get("candidates_count", len(candidates)),
            "real_candidate_count": sum(1 for item in candidates if _classify_candidate(item)),
            "all_fields_present": all(
                bool(item.get("source")) and bool(item.get("timestamp")) and bool(item.get("next_action"))
                for item in candidates
            ),
            "archive_path": payload.get("archive_path"),
            "db_path": payload.get("db_path"),
        }
    )
    runs.sort(key=lambda item: str(item.get("generated_at", "")))
    history["runs"] = runs
    history["summary"] = {
        "run_count": len(runs),
        "cron_run_count": sum(1 for item in runs if item.get("trigger_source") == "cron"),
        "manual_run_count": sum(1 for item in runs if item.get("trigger_source") == "manual"),
        "latest_generated_at": runs[-1]["generated_at"] if runs else None,
        "latest_archive_path": runs[-1]["archive_path"] if runs else None,
        "latest_day": runs[-1]["day"] if runs else None,
    }
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return history


def _write_daily_snapshot(payload: dict[str, Any], history: dict[str, Any]) -> Path:
    out_dir = ROOT / ".omo" / "_control" / "evolution" / "radar"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_day_bucket()}.json"
    snapshot = {
        "generated_at": payload["generated_at"],
        "trigger_source": payload.get("trigger_source"),
        "candidate_count": payload.get("candidates_count", 0),
        "real_candidate_count": sum(1 for item in payload.get("candidates", []) if _classify_candidate(item)),
        "archive_path": payload.get("archive_path"),
        "history": history.get("summary", {}),
    }
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


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
    return 0


def _run_mof_state_bridge_cron() -> None:
    """P5 增强: cron 跑完后跑 mof-state-bridge --strict 写 5repos 兼容字段."""
    import subprocess
    out_dir = ROOT / ".omo" / "_delivery" / "audit-rollout"
    out_dir.mkdir(parents=True, exist_ok=True)
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
    (out_dir / f"{today}-mof-state-bridge.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not in_sync:
        print(f"⚠️  mof-state-bridge 失同步: {m1_only} M1 only, written to 5repos", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
