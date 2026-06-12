#!/usr/bin/env python3
"""OPC audit-rollout 5 仓真实聚合 (P7-H3 + P4 4 仓 rollout 实证).

复验后: P4 阶段文档写 '含 4 仓 §17 metrics' 但实际 audit-rollout 只有
2 仓 (workspace + omo). P7-H3 复验: 5 仓 metrics 聚合 3 仓 n/a.

本脚本产出 5 仓真实 §17 metrics 聚合, 让 P4 阶段 4-仓声明不再被反证,
让 P7-H3 cron audit-rollout 真实有 5 仓数据.

输出 schema (与 omo cli audit-rollout 兼容):
  .omo/_delivery/audit-rollout/{date}-5repos.json
  .omo/_delivery/audit-rollout/{date}-{mode}.json (mode 透传; weekly/monthly/pre-release 各自产物)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


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
    return datetime.now(UTC).strftime("%Y-%m-%d")


def aggregate_5repos() -> dict[str, Any]:
    """调 opc_section17_metrics.py 5 仓 + 产出聚合 JSON."""
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
    }
    return summary


def main() -> int:
    payload = aggregate_5repos()
    out_dir = ROOT / ".omo" / "_delivery" / "audit-rollout"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_today()}-5repos.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"# wrote: {out_path}", file=sys.stderr)

    # mode-specific 产物 (P7-H3 acceptance: 显式写 mode-specific 文件名,
    # 让 wrapper monthly/pre-release 跑出时 mode-specific 文件名可分辨)
    # 默认 mode=weekly 与 wrapper 默认一致; 透传 OPC_MODE 让 monthly/pre-release
    # 触发时 mode-specific 文件名正确.
    mode = os.environ.get("OPC_MODE", "weekly")
    if mode not in ("weekly", "monthly", "pre-release"):
        mode = "weekly"
    mode_specific_path = out_dir / f"{_today()}-{mode}.json"
    mode_specific_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"# wrote mode-specific: {mode_specific_path} (mode={mode})", file=sys.stderr)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
