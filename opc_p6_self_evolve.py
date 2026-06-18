#!/usr/bin/env python3
"""OPC P6 self-evolution task register — 仅落 planned/, 永不入 active/.

P6-G3 红线: self-evolution task 自动 active (无 human approval) = 禁止.

实现: 读 drift detector 报告 + P5 radar, 产出 OMO planned task YAML.
  - 任何 task 状态恒为 'planned'
  - 标记 `approval_required: true` (人类审批才可 active)
  - 落 .omo/tasks/planned/OPC-P6-SELF-EVOLUTION-{n}.yaml
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.omo_io import write_text_atomic


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_latest_drift() -> dict[str, Any] | None:
    drift_dir = ROOT / ".omo" / "_control" / "evolution" / "drift"
    if not drift_dir.exists():
        return None
    files = sorted(drift_dir.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _load_latest_loop_history() -> dict[str, Any] | None:
    history_path = ROOT / ".omo" / "_control" / "evolution" / "loop" / "history.json"
    if not history_path.exists():
        return None
    try:
        return json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def emit_self_evolution_tasks() -> list[dict[str, Any]]:
    """根据 drift 报告 + radar 候选, 产出 OMO planned tasks.

    返回 tasks 列表, 每条 task 是 dict, 含 id/title/source/drift_ref/approval_required.

    latest_week 来源: 每次调用都从 .omo/_control/evolution/loop/history.json 读
    最新值, 不缓存. 这样 self-evolve 跑出时 nop task 的 latest_week 字段
    与 loop history 始终一致.
    """
    drift = _load_latest_drift()
    history = _load_latest_loop_history()
    latest_week = history.get("summary", {}).get("latest_week") if history is not None else None
    tasks: list[dict[str, Any]] = []

    if drift is not None and drift.get("drift_count", 0) > 0:
        for result in drift.get("results", []):
            if not result.get("drift"):
                continue
            kind = result["kind"]
            if kind == "entry_drift":
                for missing in result.get("missing", []):
                    tasks.append(
                        {
                            "id": f"OPC-P6-SELF-EVOLUTION-entry-{missing}",
                            "title": f"Restore cockpit scenario {missing!r} entry",
                            "source": f"drift:{kind}",
                            "drift_ref": f".omo/_control/evolution/drift/{_now_iso()[:10]}.json",
                            "approval_required": True,
                        }
                    )
            elif kind == "doc_drift":
                tasks.append(
                    {
                        "id": "OPC-P6-SELF-EVOLUTION-doc-gate-e",
                        "title": "Reconcile docs/OPC-PHASE4 with OPC-P4 plan yaml",
                        "source": f"drift:{kind}",
                        "drift_ref": f".omo/_control/evolution/drift/{_now_iso()[:10]}.json",
                        "approval_required": True,
                    }
                )
            elif kind == "duplicate_facts":
                for f in result.get("findings", []):
                    tasks.append(
                        {
                            "id": f"OPC-P6-SELF-EVOLUTION-fact-{len(tasks)}",
                            "title": f"Reconcile duplicate fact: {f[:80]}",
                            "source": f"drift:{kind}",
                            "drift_ref": f".omo/_control/evolution/drift/{_now_iso()[:10]}.json",
                            "approval_required": True,
                        }
                    )
            elif kind == "agora_bypass":
                for pat in result.get("bypass_patterns", []):
                    tasks.append(
                        {
                            "id": f"OPC-P6-SELF-EVOLUTION-bypass-{pat['file'].split('/')[-1]}",
                            "title": f"Strip agora bypass: {pat['pattern']} in {pat['file']}",
                            "source": f"drift:{kind}",
                            "drift_ref": f".omo/_control/evolution/drift/{_now_iso()[:10]}.json",
                            "approval_required": True,
                        }
                    )

    if not tasks:
        # 兜底: 即使无 drift 也生成 1 条"已闭环"task, 防止空跑
        # 红线: self-evolution task 必须 approval_required=true (即使 nop 也不能 false)
        # 错误示范: 2026-06-12 复验指出 nop task 错误标 false, 已修
        # 唯一性: 用 _now_iso() 取代日期, 同日多次跑能产生不同 ID,
        # 避免 evidence 降级为"第一份的 created_at 永不更新"
        nop_id = f"OPC-P6-SELF-EVOLUTION-nop-{_now_iso().replace(':', '').replace('-', '')}"
        tasks.append(
            {
                "id": nop_id,
                "title": "No-op: drift detector reported 0 drift; loop continues",
                "source": "drift:none",
                "drift_ref": f".omo/_control/evolution/drift/{_now_iso()[:10]}.json",
                "approval_required": True,
                "human_approval_required": True,
                "approval_state": "awaiting_human",
                "last_run_at": _now_iso(),
                "loop_history_ref": ".omo/_control/evolution/loop/history.json",
                "latest_week": latest_week,
            }
        )
    else:
        # drift > 0 路径, 给每条 task 标记 latest_week (与 loop history 对齐)
        for task in tasks:
            task["loop_history_ref"] = ".omo/_control/evolution/loop/history.json"
            task["latest_week"] = latest_week
            task["human_approval_required"] = True
            task["approval_state"] = "awaiting_human"
    return tasks


def write_planned_tasks(tasks: list[dict[str, Any]]) -> list[Path]:
    """写 tasks 到 .omo/tasks/planned/ (红线: 仅 planned/, 永不入 active/).

    返回落盘路径列表.
    """
    out_dir = ROOT / ".omo" / "tasks" / "planned"
    paths: list[Path] = []
    ts = _now_iso()
    for t in tasks:
        out = out_dir / f"{t['id']}.yaml"
        if out.exists():
            # 复用策略: 同 task ID 不重复写
            continue
        body = (
            f"id: {t['id']}\n"
            f"title: {t['title']!r}\n"  # yaml-safe quote: 含 `:`/`\n` 的 title 不会破格式
            f"status: planned\n"
            f"approval_required: {str(t['approval_required']).lower()}\n"
            f"human_approval_required: {str(t.get('human_approval_required', t['approval_required'])).lower()}\n"
            f"approval_state: {t.get('approval_state', 'awaiting_human')!r}\n"
            f"created_at: \"{ts}\"\n"
            f"source: {t['source']!r}\n"
            f"drift_ref: {t['drift_ref']!r}\n"
            f"loop_history_ref: {t.get('loop_history_ref', '.omo/_control/evolution/loop/history.json')!r}\n"
            f"review_lane: 'opc-p6-self-evolution-board'\n"
            f"prerequisite_for: OPC-P6\n"
            f"red_lines:\n"
            f"  - 'self-evolution task 仅落 planned/, 永不入 active/ 除非 human approval'\n"
            f"next_action: human reviewer approve in OMO audit queue before promoting to active/\n"
        )
        if t.get("last_run_at"):
            body += f"last_run_at: \"{t['last_run_at']}\"\n"
        if t.get("latest_week"):
            body += f"latest_week: {t['latest_week']!r}\n"
        write_text_atomic(out, body)
        paths.append(out)
    return paths


def main() -> int:
    tasks = emit_self_evolution_tasks()
    paths = write_planned_tasks(tasks)
    summary = {
        "generated_at": _now_iso(),
        "tasks_emitted": len(tasks),
        "tasks_written": len(paths),
        "red_line_held": "all tasks written to planned/ only, never active/",
        "tasks": [{"id": t["id"], "approval_required": t["approval_required"]} for t in tasks],
        "paths": [str(p.relative_to(ROOT)) for p in paths],
    }
    out_dir = ROOT / ".omo" / "_control" / "evolution" / "self-evolve"
    out_path = out_dir / f"{_now_iso()[:10]}.json"
    write_text_atomic(out_path, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    print(f"# wrote: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
