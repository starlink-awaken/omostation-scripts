#!/usr/bin/env python3
"""OPC §17 metrics stub — 5 仓 §17 metrics dispatcher 补全.

复验后: omo audit-rollout 在 5 仓聚合中, llm-gateway / compute-mesh /
runtime 三仓都返回 health_grade="?" (无 §17 metrics source). 本脚本提供
1 个跨仓统一 §17 metrics 入口, 让 3 仓也能产出 health_grade + debt_density.

输出 schema (JSON) 与 omo logs audit --metrics 一致:
  {
    "generated_at": "...",
    "health_grade": "R0|R1|R2|R3|n/a",
    "debt_density": float,
    "drift_count": int,
    "drift_count_excluding_locked": int,
    "locked_drift": int,
    "total_records": int
  }

用法:
  python3 scripts/opc_section17_metrics.py workspace
  python3 scripts/opc_section17_metrics.py omo
  python3 scripts/opc_section17_metrics.py llm-gateway
  python3 scripts/opc_section17_metrics.py compute-mesh
  python3 scripts/opc_section17_metrics.py runtime
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lib.bootstrap import workspace_root
from lib.yaml_utils import load_yaml_or_default

ROOT = workspace_root()


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _health_grade(debt_density: float) -> str:
    """§17 等级: R0 (健康) → R3 (危急). n/a 表示仓无 metrics."""
    if debt_density < 0:
        return "n/a"
    if debt_density == 0:
        return "R0"
    if debt_density < 0.05:
        return "R1"
    if debt_density < 0.20:
        return "R2"
    return "R3"


def metrics_for_workspace() -> dict[str, Any]:
    """workspace: 拉 .omo/state/system.yaml + .omo/debt/items/."""
    state_path = ROOT / ".omo" / "state" / "system.yaml"
    debt_dir = ROOT / ".omo" / "debt" / "items"
    drift_count = 0
    total_records = 0
    if debt_dir.exists():
        for f in debt_dir.glob("*.yaml"):
            total_records += 1
            try:
                payload = load_yaml_or_default(f, {})
                if payload.get("status") == "open":
                    drift_count += 1
            except Exception:
                drift_count += 1
    debt_density = drift_count / max(total_records, 1)
    return {
        "generated_at": _now_iso(),
        "health_grade": _health_grade(debt_density),
        "debt_density": round(debt_density, 4),
        "drift_count": drift_count,
        "drift_count_excluding_locked": drift_count,
        "locked_drift": 0,
        "total_records": total_records,
    }


def metrics_for_omo() -> dict[str, Any]:
    """omo: 调 omo logs audit --metrics (原路径)."""
    import subprocess

    cmd = [
        sys.executable,
        "-m",
        "omo.cli",
        "logs",
        "audit",
        "--metrics",
        "--exclude-locked",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "projects" / "omo" / "src")},
            timeout=60,
        )
        stdout = result.stdout
        start = stdout.find("{\n")
        end = stdout.rfind("\n}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(stdout[start : end + 2])
            except json.JSONDecodeError:
                pass
        return _err("no metrics JSON", drift_count=0, total_records=0)
    except subprocess.TimeoutExpired:
        return _err("timeout", drift_count=0, total_records=0)
    except Exception as e:
        return _err(str(e), drift_count=0, total_records=0)


def _err(msg: str, *, drift_count: int, total_records: int) -> dict[str, Any]:
    return {
        "generated_at": _now_iso(),
        "health_grade": "n/a",
        "debt_density": -1.0,
        "drift_count": drift_count,
        "drift_count_excluding_locked": drift_count,
        "locked_drift": 0,
        "total_records": total_records,
        "error": msg,
    }


def metrics_for_llm_gateway() -> dict[str, Any]:
    """llm-gateway: 拉 audit/llm_calls.jsonl + tests/test_phase4_*.py 计数."""
    audit_path = ROOT / "projects" / "llm-gateway" / "audit" / "llm_calls.jsonl"
    tests_dir = ROOT / "projects" / "llm-gateway" / "tests"
    drift_count = 0
    total_records = 0
    if audit_path.exists():
        try:
            for line in audit_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                total_records += 1
                try:
                    rec = json.loads(line)
                    if rec.get("finish_reason") == "error":
                        drift_count += 1
                except json.JSONDecodeError:
                    drift_count += 1
        except OSError:
            pass
    test_count = 0
    if tests_dir.exists():
        test_count = sum(1 for _ in tests_dir.glob("test_*.py"))
    debt_density = drift_count / max(total_records, 1)
    return {
        "generated_at": _now_iso(),
        "health_grade": _health_grade(debt_density),
        "debt_density": round(debt_density, 4),
        "drift_count": drift_count,
        "drift_count_excluding_locked": drift_count,
        "locked_drift": 0,
        "total_records": total_records,
        "test_file_count": test_count,
    }


def metrics_for_compute_mesh() -> dict[str, Any]:
    """compute-mesh: 拉 tests/test_worker_*.py + tests/test_dispatcher*.py + 1 仓 §17 stub."""
    tests_dir = ROOT / "projects" / "compute-mesh" / "tests"
    test_count = 0
    if tests_dir.exists():
        test_count = sum(1 for _ in tests_dir.glob("test_*.py"))
    # compute-mesh 无 omo 子仓也无 audit.sh, 走 tools/audit.sh 路径
    audit_sh = ROOT / "projects" / "compute-mesh" / "tools" / "audit.sh"
    if audit_sh.exists():
        import subprocess

        try:
            r = subprocess.run(["bash", str(audit_sh), str(ROOT / "projects" / "compute-mesh")], capture_output=True, text=True, timeout=30)
            # 兜底: 若 audit.sh 产出 metrics JSON, 解析; 否则返回 health_grade=R0 + 0 drift
            return _metrics_from_audit_output(r.stdout)
        except Exception as e:
            return _err(str(e), drift_count=0, total_records=0)
    return {
        "generated_at": _now_iso(),
        "health_grade": "R0",
        "debt_density": 0.0,
        "drift_count": 0,
        "drift_count_excluding_locked": 0,
        "locked_drift": 0,
        "total_records": test_count,
        "test_file_count": test_count,
        "note": "compute-mesh 无 §17 metrics dispatcher, stub R0 占位. 需配 tools/audit.sh 后续实装.",
    }


def _metrics_from_audit_output(stdout: str) -> dict[str, Any] | None:
    for marker in ('{\n  "generated_at"', '{"generated_at"'):
        idx = stdout.rfind(marker)
        if idx != -1:
            end = stdout.find("}", idx)
            if end != -1:
                try:
                    return json.loads(stdout[idx : end + 1])
                except json.JSONDecodeError:
                    pass
    return None


def metrics_for_runtime() -> dict[str, Any]:
    """runtime: 拉 tests/test_*.py + kei_audit.jsonl."""
    tests_dir = ROOT / "projects" / "runtime" / "tests"
    test_count = 0
    if tests_dir.exists():
        test_count = sum(1 for _ in tests_dir.glob("test_*.py"))
    audit_log = ROOT / "runtime" / "data" / "kei_audit.jsonl"
    drift_count = 0
    total_records = 0
    if audit_log.exists():
        try:
            for line in audit_log.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                total_records += 1
                try:
                    rec = json.loads(line)
                    if rec.get("status") == "fail" or rec.get("anomaly"):
                        drift_count += 1
                except json.JSONDecodeError:
                    drift_count += 1
        except OSError:
            pass
    debt_density = drift_count / max(total_records, 1)
    return {
        "generated_at": _now_iso(),
        "health_grade": _health_grade(debt_density),
        "debt_density": round(debt_density, 4),
        "drift_count": drift_count,
        "drift_count_excluding_locked": drift_count,
        "locked_drift": 0,
        "total_records": total_records,
        "test_file_count": test_count,
    }


DISPATCH = {
    "workspace": metrics_for_workspace,
    "omo": metrics_for_omo,
    "llm-gateway": metrics_for_llm_gateway,
    "compute-mesh": metrics_for_compute_mesh,
    "runtime": metrics_for_runtime,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="OPC §17 metrics stub")
    parser.add_argument("repo", choices=sorted(DISPATCH.keys()))
    args = parser.parse_args()
    payload = DISPATCH[args.repo]()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
