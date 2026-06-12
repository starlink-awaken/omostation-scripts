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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _now_iso() -> str:
    # OPC_GENERATED_AT override: 让模拟 / review 可注入语义时间点,
    # 形成真实 cadence 证据 (interval_days ≥ 7). 透传优先级:
    #   1. OPC_GENERATED_AT 环境变量 (reviewer 注入)
    #   2. wall clock (UTC now)
    override = os.environ.get("OPC_GENERATED_AT", "").strip()
    if override:
        return override
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    # 同样支持 OPC_TODAY override (与 OPC_GENERATED_AT 一致语义, 用于 review)
    override = os.environ.get("OPC_TODAY", "").strip()
    if override:
        return override
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _release_index_path() -> Path:
    return ROOT / ".omo" / "_delivery" / "release" / "index.json"


def _trigger_source() -> str:
    return os.environ.get("OPC_TRIGGER", "manual")


def _load_release_index() -> dict[str, Any]:
    path = _release_index_path()
    if not path.exists():
        return {"releases": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"releases": []}


def _next_version() -> str:
    today = _today()
    index = _load_release_index()
    todays = [item for item in index.get("releases", []) if str(item.get("version", "")).startswith(f"v{today}-r")]
    return f"v{today}-r{len(todays) + 1}"


def _update_release_index(cycle: dict[str, Any]) -> dict[str, Any]:
    index = _load_release_index()
    releases = [item for item in index.get("releases", []) if item.get("version") != cycle["version"]]
    latest_existing = releases[-1] if releases else None
    interval_days: int | None = None
    if latest_existing and latest_existing.get("generated_at"):
        try:
            current_dt = datetime.strptime(cycle["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            previous_dt = datetime.strptime(str(latest_existing["generated_at"]), "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=UTC
            )
            interval_days = (current_dt - previous_dt).days
        except ValueError:
            interval_days = None
    releases.append(
        {
            "version": cycle["version"],
            "generated_at": cycle["generated_at"],
            "trigger_source": cycle.get("trigger_source"),
            "changes_cutoff": cycle["changes"]["cutoff"],
            "commit_count": cycle["changes"]["commit_count"],
            "drift_count": cycle["validation"].get("drift", {}).get("drift_count"),
            "debt_open": cycle["debt"]["open"],
            "interval_days_from_previous": interval_days,
            "cycle_json_path": cycle["cycle_json_path"],
            "retro_path": cycle["retro_path"],
        }
    )
    releases.sort(key=lambda item: str(item["generated_at"]))
    cadence_intervals = [item["interval_days_from_previous"] for item in releases if item.get("interval_days_from_previous") is not None]
    index["releases"] = releases
    index["summary"] = {
        "release_count": len(releases),
        "latest_version": releases[-1]["version"] if releases else None,
        "cron_run_count": sum(1 for item in releases if item.get("trigger_source") == "cron"),
        "manual_run_count": sum(1 for item in releases if item.get("trigger_source") == "manual"),
        "latest_interval_days": cadence_intervals[-1] if cadence_intervals else None,
        "min_interval_days": min(cadence_intervals) if cadence_intervals else None,
        "max_interval_days": max(cadence_intervals) if cadence_intervals else None,
    }
    path = _release_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def _gather_changes() -> dict[str, Any]:
    """收集 git log 摘要作为 release notes 数据."""
    import subprocess

    index = _load_release_index()
    previous_release = index.get("releases", [])[-1] if index.get("releases") else None
    cutoff = os.environ.get(
        "OPC_RELEASE_CUTOFF",
        str(previous_release.get("generated_at")) if previous_release else "7 days ago",
    )
    result = subprocess.run(
        [
            "git",
            "log",
            f"--since={cutoff}",
            "--oneline",
            "--no-merges",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {
        "cutoff": cutoff,
        "commit_count": len(commits),
        "commits": commits[:50],
        "previous_release_version": previous_release.get("version") if previous_release else None,
    }


def _gather_validation() -> dict[str, Any]:
    """validation: 拉 5 仓 omo tests + drift detector 实证."""
    import subprocess

    out: dict[str, Any] = {}
    # 1. omo tests
    omo_test = subprocess.run(
        [
            "python3",
            "-m",
            "pytest",
            "projects/omo/tests/test_opc_p3_thin_binding_demo.py",
            "projects/omo/tests/test_opc_phase_governance_alignment.py",
            "-q",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    out["omo_tests"] = {
        "returncode": omo_test.returncode,
        "summary": omo_test.stdout.strip().splitlines()[-1] if omo_test.stdout else "",
    }
    # 2. drift detector
    drift_test = subprocess.run(
        ["python3", "scripts/opc_p6_drift_detector.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    try:
        drift_payload = json.loads(drift_test.stdout.strip())
        out["drift"] = {"kinds": drift_payload.get("kinds"), "drift_count": drift_payload.get("drift_count")}
    except json.JSONDecodeError:
        out["drift"] = {"error": "drift parse fail"}
    return out


def _gather_debt() -> dict[str, Any]:
    """debt: 拉 .omo/debt/items/ 数量 + 状态."""
    debt_dir = ROOT / ".omo" / "debt" / "items"
    if not debt_dir.exists():
        return {"total": 0, "open": 0, "resolved": 0}
    items: list[dict[str, Any]] = []
    for f in debt_dir.glob("*.yaml"):
        try:
            import yaml

            payload = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            items.append({"file": f.name, "status": payload.get("status", "unknown")})
        except Exception:
            items.append({"file": f.name, "status": "parse-fail"})
    total = len(items)
    open_count = sum(1 for i in items if i["status"] == "open")
    return {"total": total, "open": open_count, "resolved": total - open_count}


def write_release_notes(version: str, cycle: dict[str, Any]) -> Path:
    """写 release notes (含 summary/validation/debt 三件套)."""
    notes_path = ROOT / ".omo" / "_delivery" / "release" / "CHANGELOG.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    changes = cycle["changes"]
    validation = cycle["validation"]
    debt = cycle["debt"]

    summary = f"## {version} ({cycle['generated_at']})\n\n"
    summary += "### Summary\n"
    summary += f"- {changes['commit_count']} commits since {changes['cutoff']}\n"
    summary += (
        f"- Drift kinds scanned: {validation.get('drift', {}).get('kinds', '?')}, "
        f"drift_count: {validation.get('drift', {}).get('drift_count', '?')}\n"
    )
    summary += f"- Debt: total={debt['total']}, open={debt['open']}, resolved={debt['resolved']}\n\n"
    summary += "### Validation\n"
    summary += f"- omo tests: rc={validation['omo_tests']['returncode']} | {validation['omo_tests']['summary']}\n"
    summary += f"- drift detector: {validation.get('drift', {})}\n\n"
    summary += "### Debt\n"
    summary += f"- total: {debt['total']}\n"
    summary += f"- open: {debt['open']}\n"
    summary += f"- resolved: {debt['resolved']}\n\n"
    summary += "### Commits\n"
    for c in changes["commits"][:10]:
        summary += f"- {c}\n"
    summary += "\n"

    if not notes_path.exists():
        notes_path.write_text("# OPC Release Notes\n\n", encoding="utf-8")
    with notes_path.open("a", encoding="utf-8") as f:
        f.write(summary)
    return notes_path


def write_cycle_json(version: str, cycle: dict[str, Any]) -> Path:
    out_dir = ROOT / ".omo" / "_delivery" / "release"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{version}.json"
    out_path.write_text(json.dumps(cycle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def write_retrospective(version: str, cycle: dict[str, Any]) -> Path:
    retro_dir = ROOT / ".omo" / "tasks" / "registry" / "done" / "OPC-P7-H1"
    retro_dir.mkdir(parents=True, exist_ok=True)
    retro_path = retro_dir / f"retrospective-{version}.md"
    lines: list[str] = []
    lines.append(f"# OPC P7-H1 retrospective — {version}")
    lines.append("")
    lines.append(f"Generated: {cycle['generated_at']}")
    lines.append("")
    lines.append("## cycle state")
    lines.append(f"- stage: {cycle['stage']}")
    lines.append(f"- version: {version}")
    lines.append(f"- notes: {cycle.get('notes_path', '?')}")
    lines.append("")
    lines.append("## 3 字段 (summary/validation/debt)")
    lines.append("```json")
    lines.append(
        json.dumps(
            {
                "summary": {
                    "commit_count": cycle["changes"]["commit_count"],
                    "drift_count": cycle["validation"].get("drift", {}).get("drift_count"),
                },
                "validation": cycle["validation"],
                "debt": cycle["debt"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    lines.append("```")
    lines.append("")
    lines.append("## next-action")
    lines.append("- 下一周继续 release cycle")
    lines.append("- 若 drift > 0 触发 self-evolve register")
    lines.append("- H2/H3/H4/H5 同步推进")
    retro_path.write_text("\n".join(lines), encoding="utf-8")
    return retro_path


def run_one_cycle(version: str | None = None) -> dict[str, Any]:
    version = version or _next_version()
    cycle: dict[str, Any] = {
        "version": version,
        "stage": "ship",
        "generated_at": _now_iso(),
        "trigger_source": _trigger_source(),
        "cutoff": os.environ.get("OPC_RELEASE_CUTOFF", "7 days ago"),
        "changes": _gather_changes(),
        "validation": _gather_validation(),
        "debt": _gather_debt(),
    }
    cycle["notes_path"] = str(write_release_notes(version, cycle).relative_to(ROOT))
    cycle["cycle_json_path"] = str(write_cycle_json(version, cycle).relative_to(ROOT))
    cycle["retro_path"] = str(write_retrospective(version, cycle).relative_to(ROOT))
    cycle["release_index"] = _update_release_index(cycle)
    return cycle


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
