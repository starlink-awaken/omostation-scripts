#!/usr/bin/env python3
"""OPC audit-rollout 5 仓真实聚合 (P7-H3 + P4 4 仓 rollout 实证).

复验后: P4 阶段文档写 '含 4 仓 §17 metrics' 但实际 audit-rollout 只有
2 仓 (workspace + omo). P7-H3 复验: 5 仓 metrics 聚合 3 仓 n/a.

本脚本产出 5 仓真实 §17 metrics 聚合, 让 P4 阶段 4-仓声明不再被反证,
让 P7-H3 cron audit-rollout 真实有 5 仓数据.

输出 schema (与 omo cli audit-rollout 兼容):
  runtime/omo/_delivery/audit-rollout/{date}-5repos.json
  runtime/omo/_delivery/audit-rollout/{date}-{mode}.json (mode 透传; weekly/monthly/pre-release 各自产物)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lib.bootstrap import setup_omo_src, workspace_root

ROOT = workspace_root()
setup_omo_src()

from omo.omo_ingress_paths import _runtime_omo_root

REPOS = [
    ("workspace", "."),
    ("omo", "projects/omo"),
    ("llm-gateway", "projects/llm-gateway"),
    ("compute-mesh", "projects/compute-mesh"),
    ("runtime", "projects/runtime"),
]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    # OPC_GENERATED_AT override (test/语义注入时间点, 见 opc_p7 T02 设计)
    override = os.environ.get("OPC_GENERATED_AT")
    if override:
        return override
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _normalize_mode(mode: str | None) -> str:
    if mode not in ("weekly", "monthly", "pre-release"):
        return "weekly"
    return mode


def write_outputs(
    payload: dict[str, Any],
    *,
    out_dir: Path | None = None,
    today: str | None = None,
    mode: str | None = None,
) -> tuple[Path, Path]:
    """统一写 5repos baseline + mode-specific 副本.

    让 5repos.py 自身可独立测试, 不必经 daemon/fallback 才验证 mode-aware 输出契约.
    """
    target_dir = out_dir or (_runtime_omo_root(ROOT) / "_delivery" / "audit-rollout")
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = today or _today()
    normalized_mode = _normalize_mode(mode or os.environ.get("OPC_MODE", "weekly"))
    baseline_path = target_dir / f"{stamp}-5repos.json"
    mode_specific_path = target_dir / f"{stamp}-{normalized_mode}.json"
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    baseline_path.write_text(content, encoding="utf-8")
    mode_specific_path.write_text(content, encoding="utf-8")
    return baseline_path, mode_specific_path


def aggregate_5repos() -> dict[str, Any]:
    """调 opc_section17_metrics.py 5 仓 + 产出聚合 JSON.

    P4 增强 (2026-06-14): 集成 mof-state-bridge --strict 双向同步校验,
    把 .omo/tasks/ ↔ M1 OMOTask 失同步情况作为附加字段 (mof_state_bridge)
    写入 5repos.json, 让 audit-rollout 复盘 P4/P5/P6/P7 任务时能看到 OMOTask 治理.
    """
    import subprocess

    per_repo: dict[str, dict[str, Any]] = {}
    for name, rel in REPOS:
        result = subprocess.run(
            [sys.executable, "scripts/opc_section17_metrics.py", name],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0 or not result.stdout.strip():
            per_repo[name] = {
                "health_grade": "n/a",
                "debt_density": -1.0,
                "drift_count": 0,
                "total_records": 0,
                "error": f"exit={result.returncode}: {result.stderr[:120]}",
            }
            continue
        try:
            per_repo[name] = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            per_repo[name] = {"error": "JSON parse fail"}

    # P4 增强: mof-state-bridge 双向同步校验 (5repos 复盘时附带 OMOTask 治理)
    mof_state_bridge = _run_mof_state_bridge_strict()

    summary = {
        "generated_at": _now_iso(),
        "repos": per_repo,
        "summary": {
            "total_repos": len(per_repo),
            "repos_with_drift": sum(
                1
                for r in per_repo.values()
                if isinstance(r, dict) and r.get("drift_count", 0) > 0
            ),
            "repos_with_metrics": sum(
                1
                for r in per_repo.values()
                if isinstance(r, dict) and r.get("health_grade") not in ("n/a", "?")
            ),
            "repos_n_a": sum(
                1
                for r in per_repo.values()
                if isinstance(r, dict) and r.get("health_grade") in ("n/a", "?")
            ),
        },
        "mof_state_bridge": mof_state_bridge,
    }
    return summary


def _run_mof_state_bridge_strict() -> dict[str, Any]:
    """跑 mof-state-bridge --strict, 捕获 OMOTask 双向同步状态.

    返回:
    {
        "in_sync": bool,   # m1_only=0
        "m1_count": int,
        "omo_count": int,
        "paired": int,
        "drift_count": int,
        "error": str (if fail)
    }
    """
    import subprocess
    result = subprocess.run(
        [
            sys.executable,
            "projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py",
            "--json",
            "--strict",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        return {
            "in_sync": False,
            "error": f"exit={result.returncode}: {result.stderr[:200]}",
        }
    try:
        data = json.loads(result.stdout.strip())
        diff = data.get("diff", {})
        return {
            "in_sync": not bool(diff.get("m1_only", [])),
            "m1_count": data.get("m1_count", 0),
            "omo_count": data.get("omo_count", 0),
            "paired": data.get("paired", 0),
            "drift_count": len(diff.get("drifts", [])),
        }
    except json.JSONDecodeError as e:
        return {"in_sync": False, "error": f"JSON parse fail: {e}"}


def main() -> int:
    payload = aggregate_5repos()
    mode = _normalize_mode(os.environ.get("OPC_MODE", "weekly"))
    out_path, mode_specific_path = write_outputs(payload, today=_today(), mode=mode)
    print(f"# wrote: {out_path}", file=sys.stderr)
    print(f"# wrote mode-specific: {mode_specific_path} (mode={mode})", file=sys.stderr)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
