#!/usr/bin/env python3
"""OPC P7 doc lint — 关键文档 cross-ref / 字段 / 死链 / 状态漂移检测.

P7-H4: 4 关键文档自动 lint (PANORAMA/ENTRY/JOURNEY/ROADMAP) + 跨文档术语一致 + 0 stale.

本脚本实现:
  1. 关键文档 status 漂移检测 (phase plan yaml gate_status vs 文档内声明)
  2. 关键 path 是否存在 (dead-link 检测)
  3. 跨文档术语一致 (e.g. "Gate E" vs "Gate E passed")
  4. 0 stale (无未引用的旧 SSOT 引用)

输出: .omo/_delivery/doc-lint/{date}.json
       .omo/_delivery/doc-lint/{date}.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from lib.bootstrap import workspace_root, setup_omo_src

ROOT = workspace_root()
setup_omo_src()

from omo.omo_doc_lint import (
    run_doc_lint,
    utc_now_iso as _now_iso_runtime,
)


KEY_DOCS = [
    "docs/PANORAMA.md",
    "docs/ENTRY-CONVERGENCE.md",
    "docs/JOURNEY-PROBES.md",
    "docs/OPC-ROADMAP.md",
    "docs/OPC-MASTER-EXECUTION-PLAYBOOK.md",
]


PHASE_PLAN_DOCS = [
    ("P4", "OPC-P4-MODEL-COMPUTE", "docs/OPC-PHASE4-MODEL-COMPUTE.md"),
    ("P5", "OPC-P5", "docs/OPC-PHASE5-SCENARIOS.md"),
    ("P6", "OPC-P6", "docs/OPC-PHASE6-EVOLUTION-LOOP.md"),
    ("P7", "OPC-P7", "docs/OPC-PHASE7-RELEASE-TRAIN.md"),
]


def _now_iso() -> str:
    return _now_iso_runtime()


def main() -> int:
    findings, json_path, md_path = run_doc_lint(
        ROOT,
        key_docs=KEY_DOCS,
        phase_plan_docs=PHASE_PLAN_DOCS,
        generated_at=_now_iso(),
    )
    print(f"# json: {json_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"# md:   {md_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"# drift_total: {findings['drift_total']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
