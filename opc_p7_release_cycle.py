#!/usr/bin/env python3
"""OPC P7 release cycle runner — 1 个 release cycle 跑通.

P7-H1: 1-2 周周期 (cut → review → ship) + retrospective 落盘.
产出物:
  - .omo/_delivery/release/{date}-cycle.json (cycle 状态)
  - .omo/_delivery/release/CHANGELOG.md (release notes: summary/validation/debt)
  - .omo/tasks/registry/done/OPC-P7-H1/retrospective.md

red_line: release notes 必须含 summary/validation/debt 三件套.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from lib.bootstrap import workspace_root, omo_src_path

ROOT = workspace_root()
sys.path.insert(0, str(omo_src_path()))

from omo.omo_release_cycle import (
    gather_changes as _gather_changes_runtime,
    gather_debt as _gather_debt_runtime,
    gather_validation as _gather_validation_runtime,
    load_release_index as _load_release_index_runtime,
    next_release_version as _next_version_runtime,
    run_release_cycle,
    trigger_source as _trigger_source_runtime,
    utc_now_iso as _now_iso_runtime,
    utc_today as _today_runtime,
)


def _now_iso() -> str:
    return _now_iso_runtime()


def _today() -> str:
    return _today_runtime()


def _trigger_source() -> str:
    return _trigger_source_runtime()


def _load_release_index() -> dict[str, Any]:
    return _load_release_index_runtime(ROOT)


def _next_version() -> str:
    return _next_version_runtime(ROOT, _today())


def _gather_changes() -> dict[str, Any]:
    return _gather_changes_runtime(ROOT)


def _gather_validation() -> dict[str, Any]:
    return _gather_validation_runtime(ROOT)


def _gather_debt() -> dict[str, Any]:
    return _gather_debt_runtime(ROOT)


def run_one_cycle(version: str | None = None) -> dict[str, Any]:
    return run_release_cycle(
        ROOT,
        version=version,
        today=_today(),
        generated_at=_now_iso(),
        trigger=_trigger_source(),
        gather_changes_fn=_gather_changes,
        gather_validation_fn=_gather_validation,
        gather_debt_fn=_gather_debt,
    )


def main() -> int:
    version = os.environ.get("OPC_RELEASE_VERSION")
    cycle = run_one_cycle(version=version)
    print(f"# version: {cycle['version']}", file=sys.stderr)
    print(f"# notes: {cycle['notes_path']}", file=sys.stderr)
    print(f"# cycle json: {cycle['cycle_json_path']}", file=sys.stderr)
    print(f"# retro: {cycle['retro_path']}", file=sys.stderr)
    print(json.dumps(cycle, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
