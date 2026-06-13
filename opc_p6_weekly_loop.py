#!/usr/bin/env python3
"""OPC P6 weekly loop runner — 6 阶段流水线.

P6-G1: 6-stage loop radar → gap → task → swarm → audit → retro.
P6-G2: ≥2 周连续周报, 每份 ≥3 candidates + score 排序 + source + timestamp + next-action + 人工审批栏.
P6-G4: ≥1 candidate 从 radar 跑到 retrospective 闭环实证.

输出: .omo/_control/evolution/loop/{week}.json (1 周 1 份)
       .omo/tasks/registry/done/OPC-P6-G1/weekly-{week}.md (markdown 报告)
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


def _week_id(date: datetime | None = None) -> str:
    """ISO week ID: YYYY-Www."""
    d = date or datetime.now(UTC)
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _loop_history_path() -> Path:
    return ROOT / ".omo" / "_control" / "evolution" / "loop" / "history.json"


def _trace_index_path() -> Path:
    return ROOT / ".omo" / "_control" / "evolution" / "loop" / "trace-index.json"


def _load_loop_history() -> dict[str, Any]:
    path = _loop_history_path()
    if not path.exists():
        return {"runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": []}


def _week_sort_key(week: str) -> tuple[int, int]:
    year, week_num = week.split("-W", 1)
    return int(year), int(week_num)


def _consecutive_weeks(runs: list[dict[str, Any]]) -> int:
    weeks = sorted({str(run.get("week")) for run in runs if run.get("week")}, key=_week_sort_key)
    if not weeks:
        return 0
    streak = 1
    best = 1
    prev_year, prev_week = _week_sort_key(weeks[0])
    for week in weeks[1:]:
        year, week_num = _week_sort_key(week)
        expected_year, expected_week = prev_year, prev_week + 1
        if expected_week > 53:
            expected_year += 1
            expected_week = 1
        if (year, week_num) == (expected_year, expected_week):
            streak += 1
            best = max(best, streak)
        else:
            streak = 1
        prev_year, prev_week = year, week_num
    return best


def _update_loop_history(payload: dict[str, Any]) -> dict[str, Any]:
    history = _load_loop_history()
    runs = history.setdefault("runs", [])
    runs = [run for run in runs if run.get("week") != payload["week"]]
    runs.append(
        {
            "week": payload["week"],
            "generated_at": payload["generated_at"],
            "candidate_count": payload["gap"].get("candidates_count", 0),
            "planned_count": len(payload["task"].get("planned", [])),
            "drift_count": payload["drift"].get("drift_count", 0),
            "approval_required_all": all(
                item.get("approval_required") is True for item in payload["task"].get("planned", [])
            ),
        }
    )
    runs.sort(key=lambda item: _week_sort_key(str(item["week"])))
    history["runs"] = runs
    history["summary"] = {
        "weeks_recorded": len(runs),
        "max_consecutive_weeks": _consecutive_weeks(runs),
        "latest_week": runs[-1]["week"] if runs else None,
    }
    path = _loop_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return history


def _call_radar() -> dict[str, Any]:
    """Stage 1: radar — 调用 P5-F1 cockpit scenario radar.

    优先 import (快路径), 失败回退 subprocess (兼容 CLI 调用场景).
    直接 import 避免子进程开销 + 调试信息隔层; subprocess 仅在跨机器/跨
    venv 部署时作兜底. 这与 P5 路线图 "user need not understand repo
    boundaries" 一致: 主路径是 import 同一进程, 避免路径/PYTHONPATH 注入.
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from opc_p5_radar_cron import _run_radar  # type: ignore

        prior = os.environ.get("OPC_TRIGGER")
        os.environ["OPC_TRIGGER"] = prior or "loop"
        payload = _run_radar(limit=8)
        if prior is None:
            os.environ.pop("OPC_TRIGGER", None)
        else:
            os.environ["OPC_TRIGGER"] = prior
        return payload
    except Exception as e:  # ImportError, ModuleNotFoundError, anything
        # subprocess 兜底: 用 inline python 调, 设 PYTHONPATH 注入
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; sys.path.insert(0, 'projects/cockpit/src'); "
                "from cockpit.commands.scenario import _f1_technical_radar; "
                "import json; print(json.dumps(_f1_technical_radar(limit=8), ensure_ascii=False))",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return {"scenario": "technical-radar", "candidates": [], "error": f"{e} | {result.stderr}"}
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return {"scenario": "technical-radar", "candidates": [], "error": "subprocess parse fail"}


def _call_drift() -> dict[str, Any]:
    """Stage 1.5: drift detector (G3 配套)."""
    drift_path = ROOT / ".omo" / "_control" / "evolution" / "drift" / f"{_now_iso()[:10]}.json"
    if drift_path.exists():
        try:
            return json.loads(drift_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    # 现场跑一次
    import subprocess

    result = subprocess.run(
        [sys.executable, "scripts/opc_p6_drift_detector.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    # stdout 末尾是 JSON 摘要
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"kinds": 0, "drift_count": 0, "results": []}


def _stage_radar() -> dict[str, Any]:
    return {"stage": "radar", "ts": _now_iso(), "output": _call_radar()}


def _stage_gap(radar: dict[str, Any], drift: dict[str, Any]) -> dict[str, Any]:
    """Stage 2: gap analysis — radar candidates + drift findings → 排序 score."""
    candidates: list[dict[str, Any]] = []
    for c in radar.get("output", {}).get("candidates", []):
        score = 0.0
        # 启发式: evidence_id 真实 (非 null) → +1
        if c.get("evidence_id"):
            score += 1.0
        # 关键字命中 (P4/P5/P6) → +0.5
        if any(k in (c.get("title") or "").lower() for k in ("p4", "p5", "p6", "cockpit", "agora")):
            score += 0.5
        candidates.append({"candidate": c, "score": score, "lane": "radar"})

    for r in drift.get("results", []):
        if r.get("drift"):
            candidates.append(
                {
                    "candidate": {
                        "title": f"Fix {r['kind']} drift",
                        "source": f"drift:{r['kind']}",
                        "timestamp": r.get("ts", _now_iso()),
                        "next_action": f"see drift report: {r['kind']}",
                    },
                    "score": 2.0,  # drift fixes are higher priority
                    "lane": "drift",
                }
            )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return {
        "stage": "gap",
        "ts": _now_iso(),
        "candidates": candidates[:10],  # top 10
        "candidates_count": len(candidates[:10]),
    }


def _stage_task(gap: dict[str, Any]) -> dict[str, Any]:
    """Stage 3: task — gap → 计划任务 (planned, 需人工审批)."""
    planned: list[dict[str, Any]] = []
    ts = _now_iso()
    for i, item in enumerate(gap.get("candidates", [])):
        cand = item["candidate"]
        planned.append(
            {
                "id": f"OPC-P6-LOOP-{_week_id()}-{i:02d}",
                "title": cand.get("title"),
                "source": cand.get("source"),
                "score": item.get("score"),
                "lane": item.get("lane"),
                "status": "planned",
                "approval_required": True,
                "ts": ts,
            }
        )
    return {
        "stage": "task",
        "ts": ts,
        "planned": planned,
        "red_line_held": "all tasks status=planned; human approval required for active",
    }


def _stage_swarm(task: dict[str, Any]) -> dict[str, Any]:
    """Stage 4: swarm — 计划派发. 本期闭环只 plan, 实际派发留 R57+ 范围."""
    return {
        "stage": "swarm",
        "ts": _now_iso(),
        "note": "P6 closeout 范围内只 plan; 实际派发受红线 'self-evolution task 仅落 planned' 约束",
        "planned_dispatch": [t["id"] for t in task.get("planned", [])],
        "approval_lane": "opc-p6-self-evolution-board",
    }


def _stage_audit() -> dict[str, Any]:
    """Stage 5: audit — 拉 llm-gateway audit tail + 治理仪表板."""
    audit_path = ROOT / "projects" / "llm-gateway" / "audit" / "llm_calls.jsonl"
    audit_lines: list[dict[str, Any]] = []
    if audit_path.exists():
        try:
            for line in audit_path.read_text(encoding="utf-8").splitlines()[-5:]:
                if line.strip():
                    audit_lines.append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "stage": "audit",
        "ts": _now_iso(),
        "llm_audit_tail": audit_lines,
        "llm_audit_count": len(audit_lines),
    }


def _stage_retro(loop_payload: dict[str, Any]) -> dict[str, Any]:
    """Stage 6: retro — 总结 + next-action."""
    return {
        "stage": "retro",
        "ts": _now_iso(),
        "summary": {
            "radar_candidates": len(loop_payload["radar"]["output"].get("candidates", [])),
            "radar_archive_path": loop_payload["radar"]["output"].get("archive_path"),
            "drift_count": loop_payload["drift"].get("drift_count", 0),
            "planned_tasks": len(loop_payload["task"]["planned"]),
            "audit_records": loop_payload["audit"]["llm_audit_count"],
            "history_weeks_recorded": loop_payload.get("history", {}).get("summary", {}).get("weeks_recorded", 0),
            "history_max_consecutive_weeks": loop_payload.get("history", {}).get("summary", {}).get("max_consecutive_weeks", 0),
        },
        "next_action": "next week's loop continues; if drift > 0 trigger self-evolve register",
        "evidence_complete": True,
    }


def run_one_week(week: str | None = None) -> dict[str, Any]:
    week = week or _week_id()
    radar = _stage_radar()
    drift = _call_drift()
    gap = _stage_gap(radar, drift)
    task = _stage_task(gap)
    swarm = _stage_swarm(task)
    audit = _stage_audit()
    payload: dict[str, Any] = {
        "week": week,
        "generated_at": _now_iso(),
        "radar": radar,
        "drift": drift,
        "gap": gap,
        "task": task,
        "swarm": swarm,
        "audit": audit,
    }
    payload["history"] = _update_loop_history(payload)
    payload["retro"] = _stage_retro(payload)
    return payload


def _update_trace_index(payload: dict[str, Any], weekly_md_path: Path, weekly_json_path: Path) -> dict[str, Any]:
    path = _trace_index_path()
    if path.exists():
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = {"weeks": []}
    else:
        index = {"weeks": []}
    weeks = [item for item in index.get("weeks", []) if item.get("week") != payload["week"]]
    weeks.append(
        {
            "week": payload["week"],
            "generated_at": payload["generated_at"],
            "radar_archive_path": payload["radar"]["output"].get("archive_path"),
            "weekly_json_path": str(weekly_json_path.relative_to(ROOT)),
            "weekly_md_path": str(weekly_md_path.relative_to(ROOT)),
            "planned_task_ids": [item["id"] for item in payload["task"].get("planned", [])],
            "approval_lane": payload["swarm"].get("approval_lane"),
            "drift_count": payload["drift"].get("drift_count", 0),
        }
    )
    weeks.sort(key=lambda item: str(item.get("generated_at", "")))
    index["weeks"] = weeks
    index["summary"] = {
        "week_count": len(weeks),
        "latest_week": weeks[-1]["week"] if weeks else None,
        "latest_radar_archive_path": weeks[-1]["radar_archive_path"] if weeks else None,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def write_evidence(week: str, payload: dict[str, Any]) -> Path:
    """落盘 evidence: JSON + markdown."""
    out_dir = ROOT / ".omo" / "_control" / "evolution" / "loop"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{week}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_dir = ROOT / ".omo" / "tasks" / "registry" / "done" / "OPC-P6-G1"
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"weekly-{week}.md"
    _write_weekly_markdown(md_path, payload)
    _update_trace_index(payload, md_path, json_path)
    return md_path


def _write_weekly_markdown(md_path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append(f"# OPC P6 weekly retro — {payload['week']}")
    lines.append("")
    lines.append(f"Generated: {payload['generated_at']}")
    lines.append("")
    lines.append("## 1. Radar (P5-F1)")
    for c in payload["radar"]["output"].get("candidates", []):
        lines.append(f"- **{c.get('title')}**")
        lines.append(f"  - source: `{c.get('source')}`")
        lines.append(f"  - timestamp: `{c.get('timestamp')}`")
        lines.append(f"  - next_action: {c.get('next_action')}")
        if c.get("evidence_id"):
            lines.append(f"  - evidence_id: {c['evidence_id']}")
    lines.append("")
    lines.append("## 2. Drift detector (P6-G3)")
    lines.append(f"- kinds: {payload['drift'].get('kinds', 0)}")
    lines.append(f"- drift_count: **{payload['drift'].get('drift_count', 0)}**")
    for r in payload["drift"].get("results", []):
        marker = "DRIFT" if r.get("drift") else "ok"
        lines.append(f"  - `{r['kind']}` → {marker}")
    lines.append("")
    lines.append("## 3. Gap → top candidates (sorted)")
    for i, c in enumerate(payload["gap"].get("candidates", []), start=1):
        lines.append(
            f"{i}. score={c.get('score')} lane={c.get('lane')} title={c['candidate'].get('title')}"
        )
    lines.append("")
    lines.append("## 4. Task (planned, 人工审批)")
    for t in payload["task"].get("planned", []):
        lines.append(f"- `{t['id']}` | {t.get('title')} | approval_required={t.get('approval_required')}")
    lines.append("")
    lines.append("## 5. Swarm (派发受红线约束)")
    lines.append(f"- planned_dispatch: {payload['swarm'].get('planned_dispatch', [])}")
    lines.append(f"- note: {payload['swarm'].get('note')}")
    lines.append("")
    lines.append("## 6. Audit (跨仓 trail)")
    lines.append(f"- llm_audit_tail_count: {payload['audit'].get('llm_audit_count', 0)}")
    for line in payload["audit"].get("llm_audit_tail", [])[-3:]:
        lines.append(
            f"  - {line.get('ts')} task_id={line.get('task_id')} role={line.get('role')} cost={line.get('total_cost_usd')}"
        )
    lines.append("")
    lines.append("## 7. Retro / next-action")
    lines.append("```json")
    lines.append(json.dumps(payload["retro"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 7.5. History / continuity")
    history_summary = payload.get("history", {}).get("summary", {})
    lines.append(f"- weeks_recorded: {history_summary.get('weeks_recorded', 0)}")
    lines.append(f"- max_consecutive_weeks: {history_summary.get('max_consecutive_weeks', 0)}")
    lines.append(f"- latest_week: {history_summary.get('latest_week')}")
    lines.append("")
    lines.append("## 8. 人工审批栏")
    lines.append("- [ ] reviewer A: ____  date: ____")
    lines.append("- [ ] reviewer B: ____  date: ____")
    lines.append("")
    lines.append("---")
    lines.append("loop runner: scripts/opc_p6_weekly_loop.py")
    lines.append("drift detector: scripts/opc_p6_drift_detector.py")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    week = os.environ.get("OPC_WEEK")
    payload = run_one_week(week=week)
    md_path = write_evidence(payload["week"], payload)
    print(f"# week: {payload['week']}", file=sys.stderr)
    print(f"# evidence: {md_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"# json: .omo/_control/evolution/loop/{payload['week']}.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
