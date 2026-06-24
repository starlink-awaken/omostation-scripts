#!/usr/bin/env python3
"""OPC P6 drift detector — 4 类漂移检测.

P6-G3: drift detector 覆盖
  1. entry drift: cockpit scenario/radar 等入口与底层命令漂移
  2. doc drift: docs/ 文件与实际状态漂移 (e.g. "Gate E passed" 文档与 plan yaml 不一致)
  3. duplicate facts: 同一事实多份副本 (e.g. health_score 在多 yaml 中不一致)
  4. agora bypass: 业务代码绕过 agora MCP 直调 provider

输出: .omo/_control/evolution/drift/{date}.json (含 4 类状态)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "projects").exists():
    override = __import__("os").environ.get("OPC_ROOT")
    if override:
        ROOT = Path(override)

sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.omo_drift_detector import (
    build_drift_report,
    detect_agora_bypass as _detect_agora_bypass,
    detect_doc_drift as _detect_doc_drift,
    detect_duplicate_facts as _detect_duplicate_facts,
    detect_entry_drift as _detect_entry_drift,
    write_drift_report,
)


def detect_entry_drift() -> dict[str, Any]:
    return _detect_entry_drift(ROOT)


def detect_doc_drift() -> dict[str, Any]:
    return _detect_doc_drift(ROOT)


def detect_duplicate_facts() -> dict[str, Any]:
    return _detect_duplicate_facts(ROOT)


def detect_agora_bypass() -> dict[str, Any]:
    return _detect_agora_bypass(ROOT)


def main() -> int:
    summary = build_drift_report(ROOT)
    out_path = write_drift_report(ROOT, summary)
    import json

    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    print(f"# wrote: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
