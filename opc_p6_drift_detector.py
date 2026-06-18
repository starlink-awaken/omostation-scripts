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

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "projects").exists():
    # fallback: allow override via OPC_ROOT env var
    override = __import__("os").environ.get("OPC_ROOT")
    if override:
        ROOT = Path(override)

sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.omo_io import write_text_atomic
from omo.opc_phase_paths import resolve_opc_phase_task_path


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _read_yaml(rel: str) -> dict[str, Any]:
    import yaml

    return yaml.safe_load(_read(rel)) or {}


def detect_entry_drift() -> dict[str, Any]:
    """G3.1: cockpit 入口与底层命令漂移.

    已知基线: cockpit scenario {radar,assistant,health} 是 P5-F4 落地.
    """
    cli = _read("projects/cockpit/src/cockpit/cli.py")
    has_radar = (
        "scenario_sub.add_parser(\"radar\"" in cli
        or "sub.add_parser(\"radar\"" in cli
        or 'add_parser(\n        "radar"' in cli
    )
    has_assistant = (
        "scenario_sub.add_parser(\"assistant\"" in cli
        or "sub.add_parser(\"assistant\"" in cli
        or 'add_parser(\n        "assistant"' in cli
    )
    has_health = (
        "scenario_sub.add_parser(\"health\"" in cli
        or "sub.add_parser(\"health\"" in cli
        or 'add_parser(\n        "health"' in cli
    )
    missing = [name for name, present in [("radar", has_radar), ("assistant", has_assistant), ("health", has_health)] if not present]
    return {
        "kind": "entry_drift",
        "ts": _now_iso(),
        "expected": ["radar", "assistant", "health"],
        "present": [n for n, p in [("radar", has_radar), ("assistant", has_assistant), ("health", has_health)] if p],
        "missing": missing,
        "drift": len(missing) > 0,
    }


def detect_doc_drift() -> dict[str, Any]:
    """G3.2: docs/ 文档与 plan yaml 漂移.

    检测: docs/OPC-PHASE4-MODEL-COMPUTE.md 与 .omo/tasks/planned/OPC-P4-MODEL-COMPUTE.yaml
    的 gate_status 是否一致.
    """
    plan_rel = str(resolve_opc_phase_task_path(ROOT, "OPC-P4-MODEL-COMPUTE").relative_to(ROOT))
    plan = _read_yaml(plan_rel)
    plan_gate_status = plan.get("gate_status")
    phase_doc = _read("docs/OPC-PHASE4-MODEL-COMPUTE.md")
    doc_says_passed = "Gate E passed" in phase_doc and "opc_phase4_gate_e_passed" in phase_doc
    consistent = plan_gate_status == "passed" and doc_says_passed
    return {
        "kind": "doc_drift",
        "ts": _now_iso(),
        "plan_ref": plan_rel,
        "plan_gate_status": plan_gate_status,
        "doc_says_passed": doc_says_passed,
        "consistent": consistent,
        "drift": not consistent,
    }


def detect_duplicate_facts() -> dict[str, Any]:
    """G3.3: duplicate facts 漂移.

    已知重复: health_score 同时出现在 .omo/state/system.yaml
    (显示分 82.0) 和 raw 100.0, 不应被多个 yaml 覆盖.
    这里简化为检测: 同一 key 在 system.yaml + goals/current.yaml 中
    是否有不一致声明.
    """
    sys_state = _read_yaml(".omo/state/system.yaml")
    goals = _read_yaml(".omo/goals/current.yaml")
    sys_health = sys_state.get("health_score")
    findings: list[str] = []
    if isinstance(sys_health, (int, float)) and sys_health < 100 and goals:
        # 治理视角 6 项分 (maturity/safety 等) 应都是 100, 整体 health 不应是 82
        maturity = goals.get("governance", {}).get("ecosystem_maturity_score")
        if maturity == 100 and sys_health < 100:
            findings.append(
                f"system.yaml health_score={sys_health} but goals.governance.ecosystem_maturity_score=100"
            )
    return {
        "kind": "duplicate_facts",
        "ts": _now_iso(),
        "findings": findings,
        "drift": len(findings) > 0,
    }


def detect_agora_bypass() -> dict[str, Any]:
    """G3.4: 业务代码绕过 agora MCP 直调 provider.

    检测: 业务模块 (projects/runtime, projects/cockpit) 是否
    直接 import openai/anthropic/vertexai 或子进程跑 inference.
    已知基线: llm-gateway 是唯一 provider 抽象.
    """
    bypass_patterns: list[dict[str, str]] = []
    forbidden_imports = (
        "from openai import",
        "import openai",
        "from anthropic import",
        "import anthropic",
        "from vertexai",
        "import vertexai",
    )
    for rel in [
        "projects/runtime/src/runtime/executor/engine.py",
        "projects/cockpit/src/cockpit/commands/scenario.py",
        "projects/runtime/src/runtime/executor/config/__init__.py",
    ]:
        try:
            content = _read(rel)
        except FileNotFoundError:
            continue
        for pat in forbidden_imports:
            if pat in content:
                bypass_patterns.append({"file": rel, "pattern": pat})
    return {
        "kind": "agora_bypass",
        "ts": _now_iso(),
        "scanned_files": [
            "projects/runtime/src/runtime/executor/engine.py",
            "projects/cockpit/src/cockpit/commands/scenario.py",
            "projects/runtime/src/runtime/executor/config/__init__.py",
        ],
        "bypass_patterns": bypass_patterns,
        "drift": len(bypass_patterns) > 0,
    }


def main() -> int:
    detectors = [
        detect_entry_drift,
        detect_doc_drift,
        detect_duplicate_facts,
        detect_agora_bypass,
    ]
    results: list[dict[str, Any]] = [detector() for detector in detectors]
    summary = {
        "generated_at": _now_iso(),
        "kinds": len(results),
        "drift_count": sum(1 for r in results if r["drift"]),
        "results": results,
    }
    out_dir = ROOT / ".omo" / "_control" / "evolution" / "drift"
    # 时间戳到秒, 避免同日多次跑相互覆盖 (复验 反馈: 同日同文件覆盖丢证据)
    out_path = out_dir / f"{datetime.now(UTC).strftime('%Y-%m-%dT%H%M%S')}.json"
    write_text_atomic(out_path, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    print(f"# wrote: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
