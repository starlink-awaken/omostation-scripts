#!/usr/bin/env python3
"""OPC P7 phase gate 自动检查 — 8 phase × Gate A-H 状态矩阵.

P7-H2: check_phase_gate.py 跑通 + 8 Gate acceptance 自动检查 + audit 写入.

产出:
  .omo/_delivery/phase-gate/{date}.json  (8 phase × gate 矩阵)
  .omo/_delivery/phase-gate/{date}.md    (人类可读报告)
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.omo_phase_gate import write_phase_gate_audit
from omo.opc_phase_paths import PHASE_TASK_IDS, resolve_opc_phase_task_path


PHASES = [
    ("P0", "Gate A", ".omo/tasks/done/OPC-P0-BASELINE.yaml", None),
    ("P1", "Gate B", ".omo/tasks/done/OPC-P1-ENTRY-CONVERGENCE.yaml", None),
    ("P1.5", "Gate B2", ".omo/tasks/done/OPC-P15-GOVERNANCE.yaml", None),
    ("P2", "Gate C", ".omo/tasks/done/OPC-P2-GATE-C.yaml", None),
    ("P3", "Gate D", None, "OPC-P3-GATE-D-OPENING"),
    ("P4", "Gate E", None, "OPC-P4-MODEL-COMPUTE"),
    ("P5", "Gate F", None, "OPC-P5"),
    ("P6", "Gate G", None, "OPC-P6"),
    ("P7", "Gate H", None, "OPC-P7"),
]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_yaml(rel: str) -> dict[str, Any] | None:
    import yaml

    p = ROOT / rel
    if not p.exists():
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _check_phase(phase: str, gate: str, plan_rel: str | None, task_id: str | None) -> dict[str, Any]:
    resolved_rel = plan_rel
    if task_id:
        try:
            resolved_rel = str(resolve_opc_phase_task_path(ROOT, task_id).relative_to(ROOT))
        except FileNotFoundError:
            resolved_rel = plan_rel or f".omo/tasks/*/{task_id}.yaml"
    payload = _read_yaml(resolved_rel) if resolved_rel else None
    if payload is None:
        return {
            "phase": phase,
            "gate": gate,
            "plan_file": resolved_rel,
            "exists": False,
            "gate_status": "missing",
            "passed": False,
            "sub_gate_count": 0,
            "sub_gate_passed": 0,
            "sub_gate_open": 0,
        }
    gate_status = payload.get("gate_status", "unknown")
    sub_gates = payload.get("sub_gates", [])
    if isinstance(sub_gates, list):
        sg_passed = sum(1 for sg in sub_gates if isinstance(sg, dict) and sg.get("status") == "passed")
        sg_open = sum(1 for sg in sub_gates if isinstance(sg, dict) and sg.get("status") in {"not_started", "not_yet_passed"})
    else:
        sg_passed = 0
        sg_open = 0
    return {
        "phase": phase,
        "gate": gate,
        "plan_file": resolved_rel,
        "exists": True,
        "gate_status": gate_status,
        "passed": gate_status == "passed",
        "sub_gate_count": len(sub_gates) if isinstance(sub_gates, list) else 0,
        "sub_gate_passed": sg_passed,
        "sub_gate_open": sg_open,
    }


def build_matrix() -> dict[str, Any]:
    rows = [_check_phase(p, g, rel, task_id) for p, g, rel, task_id in PHASES]
    summary = {
        "phases_total": len(rows),
        "phases_passed": sum(1 for r in rows if r["passed"]),
        "phases_open": sum(1 for r in rows if not r["passed"]),
    }
    return {"generated_at": _now_iso(), "summary": summary, "rows": rows}


def write_audit(payload: dict[str, Any]) -> tuple[Path, Path]:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return write_phase_gate_audit(ROOT, payload, today)


def main() -> int:
    payload = build_matrix()
    json_path, md_path = write_audit(payload)
    print(f"# json: {json_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"# md:   {md_path.relative_to(ROOT)}", file=sys.stderr)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
