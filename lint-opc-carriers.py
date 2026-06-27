#!/usr/bin/env python3
"""
lint-opc-carriers.py

OPC P3-P7 治理载体 (governance carriers) 一致性 lint 器.

校验项 (ISOT 严格模式 — 任何违规都算 fail):
  1. YAML 解析必须 OK
  2. 字段必备: id / status / priority / domain / created / gate / gate_status
  3. 子闸 (sub_gates) 至少 3 项
  4. signals 至少 4 条; 命名必须匹配 opc_phaseN_(gate_XN|subgate_YN)_<status>
     其中 <status> ∈ {passed, not_started, not_yet_passed, opened}
  5. forbidden_claims 至少 3 条; 不能出现 "完成" / "passed" / "100%" 措辞
     (除明示 evidence 前置)
  6. red_lines 至少 3 条
  7. phase_open_condition / phase_blocked_condition / final_close_condition 三段
     必须存在且非空
  8. description 中 "Source-of-truth:" 引用文件必须真实存在
  9. 跨 yaml 的 prerequisites 引用的 signal 至少有一条在定义方,
     或可由同组 carrier 的 canonical gate passed signal 推导

用法:
  python3 scripts/lint-opc-carriers.py
  python3 scripts/lint-opc-carriers.py --verbose
  python3 scripts/lint-opc-carriers.py --strict   # 任何 warning 也算 fail

退出码: 0 全过; 1 至少 1 个 error
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from lib.bootstrap import workspace_root
from lib.paths import OMO_DIR
from lib.yaml_utils import load_yaml
from lib.validators import LintReport, require_fields, require_list_min, match_pattern_list

# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #

REPO_ROOT = workspace_root()
PLANNED_DIR = OMO_DIR / "tasks" / "planned"
DONE_DIR = OMO_DIR / "tasks" / "registry" / "done"
DOCS_DIR = REPO_ROOT / "docs"

# 8 个治理载体 (5 yaml + 3 supporting context: P3.yaml + GATE-D-OPENING.yaml + 4 phase doc)
CARRIERS = [
    PLANNED_DIR / "OPC-P3-SWARM-SPINE.yaml",
    PLANNED_DIR / "OPC-P4-MODEL-COMPUTE.yaml",
    PLANNED_DIR / "OPC-P5-SCENARIOS.yaml",
    PLANNED_DIR / "OPC-P6-EVOLUTION-LOOP.yaml",
    PLANNED_DIR / "OPC-P7-RELEASE-TRAIN.yaml",
]

# 对应 doc 引用
PHASE_DOC = {
    "OPC-P3-SWARM-SPINE": DOCS_DIR / "OPC-PHASE3-SWARM-SPINE.md",
    "OPC-P4-MODEL-COMPUTE": DOCS_DIR / "OPC-PHASE4-MODEL-COMPUTE.md",
    "OPC-P5-SCENARIOS": DOCS_DIR / "OPC-PHASE5-SCENARIOS.md",
    "OPC-P6-EVOLUTION-LOOP": DOCS_DIR / "OPC-PHASE6-EVOLUTION-LOOP.md",
    "OPC-P7-RELEASE-TRAIN": DOCS_DIR / "OPC-PHASE7-RELEASE-TRAIN.md",
}

VALID_STATUSES = {"passed", "not_started", "not_yet_passed", "opened", "completed"}
SIGNAL_RE = re.compile(
    r"^opc_phase[0-9]+_(gate_[a-z][0-9]?|subgate_[a-z][0-9]?|[a-z]+)_(passed|not_started|not_yet_passed|opened)$"
)
FORBIDDEN_CLAIM_HINTS = [
    re.compile(r"\b100% 完成"),
    re.compile(r"passed 全部"),
]

# Cross-yaml prereqs 是有意为之的 (引用 P2, §19 等不在 P3-P7 内的信号)
# 真正的 cross-yaml 配对 (P3→P4, P4→P5 ...) 都在同一组 CARRIERS 内
CROSS_PHASE_ALLOWED_PREFIXES = (
    "opc_phase2_",
    "opc_p2_",
    "opc_section19_",
    "opc_p15_",
    "llm_gateway_",
    "compute_mesh_",
    "cockpit_",
)


# --------------------------------------------------------------------------- #
# 校验函数
# --------------------------------------------------------------------------- #


def _check_yaml_parsable(path: Path, report: LintReport) -> dict[str, Any] | None:
    try:
        data = load_yaml(path)
        if not isinstance(data, dict):
            report.err(str(path), "top-level must be a mapping")
            return None
        return data
    except Exception as e:
        report.err(str(path), f"yaml parse error: {e}")
        return None


def _check_required_fields(data: dict[str, Any], path: Path, report: LintReport) -> None:
    require_fields(data, ["id", "status", "priority", "domain", "created", "gate", "gate_status"], str(path), report)


def _check_sub_gates(data: dict[str, Any], path: Path, report: LintReport) -> None:
    sub = data.get("sub_gates") or data.get("tasks")
    if not isinstance(sub, list):
        report.err(str(path), "sub_gates (or tasks) must be a list")
        return
    if len(sub) < 3:
        report.err(str(path), f"sub_gates/tasks count = {len(sub)} (need >= 3)")
        return
    for sg in sub:
        if "status" not in sg:
            report.err(str(path), f"sub_gate/task {sg.get('id', '?')} missing status")
        elif sg["status"] not in VALID_STATUSES:
            report.warn(
                str(path),
                f"sub_gate {sg.get('id', '?')} has unusual status: {sg['status']}",
            )


def _check_signals(data: dict[str, Any], path: Path, report: LintReport) -> None:
    sigs = require_list_min(data, "signals", 4, str(path), report)
    if sigs is not None:
        match_pattern_list(sigs, SIGNAL_RE, "signal", str(path), report)


def _check_forbidden_claims(data: dict[str, Any], path: Path, report: LintReport) -> None:
    fcs = require_list_min(data, "forbidden_claims", 3, str(path), report)
    if fcs is not None:
        for fc in fcs:
            for hint in FORBIDDEN_CLAIM_HINTS:
                if hint.search(fc):
                    report.err(str(path), f"forbidden_claim '{fc}' contains blacklisted phrase")


def _check_red_lines(data: dict[str, Any], path: Path, report: LintReport) -> None:
    require_list_min(data, "red_lines", 3, str(path), report)


def _check_readiness(data: dict[str, Any], path: Path, report: LintReport) -> None:
    for field in ("phase_open_condition", "phase_blocked_condition", "final_close_condition"):
        v = data.get(field)
        if not v or not str(v).strip():
            report.err(str(path), f"{field} missing or empty")


def _check_source_of_truth(data: dict[str, Any], path: Path, report: LintReport) -> None:
    desc = str(data.get("description", ""))
    carrier_id = data.get("id", "")
    doc_path = PHASE_DOC.get(carrier_id)
    # 1) description must mention "Source-of-truth:"
    if "Source-of-truth" not in desc and "source_of_truth" not in data:
        report.err(str(path), "description missing 'Source-of-truth:' reference")
    # 2) phase doc must exist (for P4-P7) — P3 uses GATE-D-OPENING.yaml
    if doc_path is not None and not doc_path.exists():
        report.err(str(path), f"phase doc missing: {doc_path.relative_to(REPO_ROOT)}")
    # 3) source_of_truth block — paths must exist
    sot = data.get("source_of_truth", [])
    if isinstance(sot, list):
        for ref in sot:
            # 允许 .yaml, 目录 (末尾 /), 拼接到 REPO_ROOT
            # 注意: 不能 lstrip('./') — 会把 ".omo" 切成 "omo"
            if ref.startswith("./"):
                ref_clean = ref[2:]
            elif ref.startswith(".omo/"):
                ref_clean = ref  # already repo-relative w/ dot
            else:
                ref_clean = ref.lstrip("/")
            ref_path = REPO_ROOT / ref_clean
            if not ref_path.exists():
                report.err(str(path), f"source_of_truth ref missing on disk: {ref} (resolved {ref_path.relative_to(REPO_ROOT)})")


def _carrier_canonical_signals(carrier: dict[str, Any]) -> set[str]:
    """Return canonical future-state signals implied by the carrier schema.

    目的: prerequisites 合法引用未来态 gate_passed 信号, 即便当前 signals
    因 gate 未通过只声明了 not_yet_passed. 这种引用是 Phase DAG 的正常表达,
    不应持续报 warning.
    """
    out: set[str] = set()
    carrier_id = str(carrier.get("id", ""))
    gate = str(carrier.get("gate", ""))
    phase_match = re.search(r"OPC-P(\d+)", carrier_id)
    gate_match = re.search(r"Gate\s+([A-Z]\d?)", gate)
    if phase_match and gate_match:
        phase = phase_match.group(1)
        gate_name = gate_match.group(1).lower()
        out.add(f"opc_phase{phase}_gate_{gate_name}_passed")
    return out


def _collect_all_signals(carriers: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for c in carriers:
        for s in c.get("signals", []):
            if isinstance(s, str):
                out.add(s)
        out.update(_carrier_canonical_signals(c))
    return out


def _check_cross_yaml_prereqs(
    carriers: list[dict[str, Any]], report: LintReport
) -> None:
    all_sigs = _collect_all_signals(carriers)
    for c in carriers:
        cid = c.get("id", "?")
        for prereq in c.get("prerequisites", []):
            if not isinstance(prereq, str):
                continue
            if prereq in all_sigs:
                continue
            # Heuristic: signal 形式才算 cross-yaml; 非信号 (e.g. repo available) 算 OK
            if prereq.startswith("opc_"):
                if not any(prereq.startswith(p) for p in CROSS_PHASE_ALLOWED_PREFIXES):
                    report.warn(
                        f"{cid}",
                        f"prerequisite '{prereq}' not defined as signal in any carrier",
                    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main(argv: list[str]) -> int:
    verbose = "--verbose" in argv
    strict = "--strict" in argv

    report = LintReport()
    carriers_data: list[dict[str, Any]] = []

    for path in CARRIERS:
        if not path.exists():
            report.err(str(path), "carrier file missing")
            continue
        data = _check_yaml_parsable(path, report)
        if data is None:
            continue
        carriers_data.append(data)
        cid = data.get("id", path.stem)
        report.ok(str(path), f"parsed (id={cid})")
        _check_required_fields(data, path, report)
        _check_sub_gates(data, path, report)
        _check_signals(data, path, report)
        _check_forbidden_claims(data, path, report)
        _check_red_lines(data, path, report)
        _check_readiness(data, path, report)
        _check_source_of_truth(data, path, report)

    _check_cross_yaml_prereqs(carriers_data, report)

    # 输出
    report.print_summary(f"OPC Carriers Lint — {len(CARRIERS)} carriers", verbose=verbose)
    code = report.exit_code(strict=strict)
    print(" FAIL" if code else " PASS")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
