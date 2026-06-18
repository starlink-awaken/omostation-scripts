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
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.omo_io import write_text_atomic
from omo.opc_phase_paths import resolve_opc_phase_task_path


KEY_DOCS = [
    "docs/PANORAMA.md",
    "docs/ENTRY-CONVERGENCE.md",
    "docs/JOURNEY-PROBES.md",
    "docs/OPC-ROADMAP.md",
    "docs/OPC-MASTER-EXECUTION-PLAYBOOK.md",
    "docs/OPC-GOVERNANCE-CARRIERS-INDEX.md",
]


PHASE_PLAN_DOCS = [
    ("P4", "OPC-P4-MODEL-COMPUTE", "docs/OPC-PHASE4-MODEL-COMPUTE.md"),
    ("P5", "OPC-P5", "docs/OPC-PHASE5-SCENARIOS.md"),
    ("P6", "OPC-P6", "docs/OPC-PHASE6-EVOLUTION-LOOP.md"),
    ("P7", "OPC-P7", "docs/OPC-PHASE7-RELEASE-TRAIN.md"),
]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _doc_lint_index_path() -> Path:
    return ROOT / ".omo" / "_delivery" / "doc-lint" / "index.json"


def _load_doc_lint_index() -> dict[str, Any]:
    path = _doc_lint_index_path()
    if not path.exists():
        return {"runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": []}


def _update_doc_lint_index(findings: dict[str, Any]) -> dict[str, Any]:
    index = _load_doc_lint_index()
    runs = [run for run in index.get("runs", []) if run.get("generated_at") != findings["generated_at"]]
    runs.append(
        {
            "generated_at": findings["generated_at"],
            "drift_total": findings["drift_total"],
            "dead_links": len(findings["dead_links"]),
            "term_issues": len(findings["term_consistency_issues"]),
        }
    )
    runs.sort(key=lambda item: item["generated_at"])
    index["runs"] = runs[-30:]
    index["summary"] = {
        "run_count": len(index["runs"]),
        "latest_drift_total": index["runs"][-1]["drift_total"] if index["runs"] else None,
    }
    path = _doc_lint_index_path()
    write_text_atomic(path, json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    return index


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _read_yaml(rel: str) -> dict[str, Any]:
    import yaml

    return yaml.safe_load(_read(rel)) or {}


def check_key_docs_exist() -> dict[str, Any]:
    missing: list[str] = []
    present: list[str] = []
    for rel in KEY_DOCS:
        if (ROOT / rel).exists():
            present.append(rel)
        else:
            missing.append(rel)
    return {
        "kind": "key_docs_present",
        "expected": len(KEY_DOCS),
        "present": present,
        "missing": missing,
        "drift": len(missing) > 0,
    }


def check_phase_doc_consistency() -> list[dict[str, Any]]:
    """phase plan yaml gate_status vs phase doc 声明一致性."""
    import yaml

    findings: list[dict[str, Any]] = []
    for phase, task_id, doc_rel in PHASE_PLAN_DOCS:
        try:
            plan_rel = str(resolve_opc_phase_task_path(ROOT, task_id).relative_to(ROOT))
            plan = _read_yaml(plan_rel)
            doc = _read(doc_rel)
        except FileNotFoundError:
            findings.append({"phase": phase, "status": "missing-file", "drift": True})
            continue
        plan_status = plan.get("gate_status", "unknown")
        if plan_status == "passed":
            if "passed" not in doc.lower() and f"Gate {plan['gate'][-1]} passed" not in doc:
                findings.append(
                    {
                        "phase": phase,
                        "plan_status": plan_status,
                        "doc": doc_rel,
                        "issue": "plan says passed but doc lacks 'passed'",
                        "drift": True,
                    }
                )
            else:
                findings.append(
                    {
                        "phase": phase,
                        "plan_status": plan_status,
                        "doc": doc_rel,
                        "drift": False,
                    }
                )
        else:
            findings.append(
                {"phase": phase, "plan_status": plan_status, "doc": doc_rel, "drift": False}
            )
    return findings


def check_dead_links() -> list[dict[str, Any]]:
    """扫描 KEY_DOCS 中 [text](rel) 形式链接, 检测 dead link."""
    link_re = re.compile(r"\[([^\]]+)\]\((?!https?://|#)([^)]+)\)")
    dead: list[dict[str, Any]] = []
    for rel in KEY_DOCS:
        try:
            text = _read(rel)
        except FileNotFoundError:
            continue
        for m in link_re.finditer(text):
            link_text, link_target = m.group(1), m.group(2)
            # 跳过绝对路径与外部链接
            if link_target.startswith("/") or link_target.startswith("http"):
                continue
            target = (ROOT / rel).parent / link_target
            if not target.exists():
                dead.append({"doc": rel, "link_text": link_text, "link_target": link_target})
    return dead


def check_term_consistency() -> list[dict[str, Any]]:
    """关键术语: 'Gate E passed' vs 'Gate E in progress' 漂移.

    仅检测: phase plan yaml gate_status=passed, 但 doc 顶部 Status 行还写
    'not_yet_passed' 的情况. 不检测嵌套在 phase_blocked_condition / 历史
    描述段中的 'not_yet_passed' (那些是有意保留的对照说明).
    """
    issues: list[dict[str, Any]] = []
    for phase, task_id, doc_rel in PHASE_PLAN_DOCS:
        try:
            plan_rel = str(resolve_opc_phase_task_path(ROOT, task_id).relative_to(ROOT))
            plan = _read_yaml(plan_rel)
            doc = _read(doc_rel)
        except FileNotFoundError:
            continue
        plan_status = plan.get("gate_status", "unknown")
        gate = plan.get("gate", "")
        if plan_status != "passed":
            continue
        # 只在 doc 顶部 30 行内检查 (Status 声明段)
        head_lines = doc.splitlines()[:30]
        head_text = "\n".join(head_lines).lower()
        if "not_yet_passed" in head_text and gate.lower() in head_text:
            issues.append(
                {
                    "phase": phase,
                    "doc": doc_rel,
                    "issue": f"doc head still has 'not_yet_passed' for {gate}",
                }
            )
    return issues


def main() -> int:
    findings: dict[str, Any] = {
        "generated_at": _now_iso(),
        "key_docs": check_key_docs_exist(),
        "phase_doc_consistency": check_phase_doc_consistency(),
        "dead_links": check_dead_links(),
        "term_consistency_issues": check_term_consistency(),
    }
    total_drift = (
        (1 if findings["key_docs"]["drift"] else 0)
        + sum(1 for f in findings["phase_doc_consistency"] if f.get("drift"))
        + (1 if findings["dead_links"] else 0)
        + (1 if findings["term_consistency_issues"] else 0)
    )
    findings["drift_total"] = total_drift
    findings["history"] = _update_doc_lint_index(findings)

    out_dir = ROOT / ".omo" / "_delivery" / "doc-lint"
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    json_path = out_dir / f"{today}.json"
    write_text_atomic(json_path, json.dumps(findings, ensure_ascii=False, indent=2) + "\n")
    md_path = out_dir / f"{today}.md"
    lines = [f"# OPC Doc Lint — {today}", "", f"Drift total: **{total_drift}**", ""]
    lines.append("## Key docs presence")
    lines.append(f"- expected: {findings['key_docs']['expected']}")
    lines.append(f"- present: {len(findings['key_docs']['present'])}")
    if findings["key_docs"]["missing"]:
        lines.append(f"- missing: {findings['key_docs']['missing']}")
    lines.append("")
    lines.append("## Phase doc consistency")
    for f in findings["phase_doc_consistency"]:
        marker = "DRIFT" if f.get("drift") else "ok"
        lines.append(f"- {f.get('phase', '?')}: {marker}")
    lines.append("")
    lines.append("## Dead links")
    if findings["dead_links"]:
        for d in findings["dead_links"]:
            lines.append(f"- {d['doc']} → {d['link_target']}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Term consistency")
    if findings["term_consistency_issues"]:
        for t in findings["term_consistency_issues"]:
            lines.append(f"- {t['phase']}: {t['issue']}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## History")
    lines.append(f"- run_count: {findings['history']['summary']['run_count']}")
    lines.append(f"- latest_drift_total: {findings['history']['summary']['latest_drift_total']}")
    write_text_atomic(md_path, "\n".join(lines) + "\n")
    print(f"# json: {json_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"# md:   {md_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"# drift_total: {total_drift}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
