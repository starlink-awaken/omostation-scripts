#!/usr/bin/env python3
"""跨项目健康检查 — 全量测试 + lint + Git 状态 每日报告。

Usage:
    python3 scripts/health_scan.py

Scans all active projects under ~/Workspace/projects/, runs tests and lint,
outputs a markdown health table to stdout. Designed for daily cron.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from lib.bootstrap import workspace_root

WORKSPACE = workspace_root()
PROJECTS_DIR = WORKSPACE / "projects"

# Projects that are known to have test suites
ACTIVE_PROJECTS: list[dict] = [
    # (dir_name, test_path, src_path, label)
    {"dir": "ecos", "test": "tests", "src": "src", "label": "ecos L0"},
    {"dir": "cockpit", "test": "src/cockpit/tests", "src": "src/cockpit", "label": "cockpit L3"},
    {"dir": "agora", "test": "tests", "src": "src/agora", "label": "agora I0"},
    {"dir": "omo", "test": "tests", "src": "src/omo", "label": "omo L2"},
    {"dir": "metaos", "test": "tests", "src": "src/metaos", "label": "metaos L2"},
    {"dir": "runtime", "test": "tests", "src": "src/runtime", "label": "runtime L1"},
    {"dir": "kairon", "test": "", "src": "packages", "label": "kairon L2",
     "test_cmd": "make test-fast"},
    {"dir": "aetherforge", "test": "tests", "src": "src/aetherforge", "label": "aetherforge X"},
    {"dir": "model-driven", "test": "tests", "src": "src/model_driven", "label": "model-driven X"},
    {"dir": "c2g", "test": "tests", "src": "src/c2g", "label": "c2g X"},
    {"dir": "omo-debt", "test": "tests", "src": "src/omo_debt", "label": "omo-debt X"},
    {"dir": "l4-kernel", "test": "tests", "src": "src/l4_kernel", "label": "l4-kernel L4"},
]


def _run(cmd: list[str], cwd: Path, timeout: int = 120) -> dict:
    """Run a command and return result dict."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, cwd=str(cwd))
        return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr,
                "exit": r.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"TIMEOUT ({timeout}s)", "exit": -1}
    except FileNotFoundError as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "exit": -1}


def scan_project(proj: dict) -> dict:
    """Scan a single project. Returns result dict."""
    proj_dir = PROJECTS_DIR / proj["dir"]
    result = {"label": proj["label"], "dir": proj["dir"], "tests": {}, "lint": {}, "git": {}}

    if not proj_dir.exists():
        result["error"] = "directory not found"
        return result

    # ── Git status ────────────────────────────────────
    g = _run(["git", "status", "--porcelain"], cwd=proj_dir, timeout=10)
    changed = [line for line in g["stdout"].splitlines() if line.strip()]
    result["git"]["uncommitted"] = len(changed)
    result["git"]["branch"] = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=proj_dir, timeout=5
    ).get("stdout", "").strip()

    # ── Tests ─────────────────────────────────────────
    test_cmd = proj.get("test_cmd", "")
    if test_cmd:
        t = _run(test_cmd.split(), cwd=proj_dir, timeout=300)
    elif proj["test"]:
        t = _run(["uv", "run", "pytest", proj["test"], "-q", "--tb=no"],
                 cwd=proj_dir, timeout=300)
    else:
        t = {"ok": True, "stdout": "no tests configured"}

    # Parse pytest output: "N passed, M failed, K skipped"
    last_line = [line for line in t["stdout"].splitlines() if line.strip()][-1:] if t["stdout"] else []
    result["tests"]["output"] = last_line[0] if last_line else t["stdout"][:100]
    result["tests"]["ok"] = t["ok"]

    # Parse numbers
    import re
    for line in t["stdout"].splitlines():
        m = re.search(r"(\d+) passed", line)
        if m:
            result["tests"]["passed"] = int(m.group(1))
        m = re.search(r"(\d+) failed", line)
        if m:
            result["tests"]["failed"] = int(m.group(1))
        m = re.search(r"(\d+) skipped", line)
        if m:
            result["tests"]["skipped"] = int(m.group(1))
    if "passed" not in result["tests"] and t["ok"]:
        result["tests"]["passed"] = "ok"

    # ── Ruff lint ─────────────────────────────────────
    if proj["src"]:
        lint_result = _run(["uv", "run", "ruff", "check", proj["src"], "--statistics"],
                 cwd=proj_dir, timeout=30)
        result["lint"]["ok"] = lint_result["ok"]
        lint_lines = [x for x in lint_result["stdout"].splitlines() if x.strip()]
        result["lint"]["errors"] = len(lint_lines) if not lint_result["ok"] else 0

    return result


def main():
    print("# 跨项目健康报告\n")
    print(f"_生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}_\n")

    results = []
    for proj in ACTIVE_PROJECTS:
        r = scan_project(proj)
        results.append(r)

    # ── Summary table ─────────────────────────────────
    print("## 测试基线\n")
    print("| 项目 | 分层 | 测试结果 | Lint | Git |")
    print("|------|------|---------|------|-----|")
    for r in results:
        t = r["tests"]
        tests_str = (f"{t.get('passed', '?')}p/{t.get('failed', 0)}f"
                     f"{'/' + str(t.get('skipped', 0)) + 's' if t.get('skipped') else ''}")
        if not t.get("ok") and t.get("passed") is None:
            tests_str = f"⚠️ {t.get('output', '?')[:30]}"

        lint_str = "✅" if r["lint"].get("ok") else f"❌ {r['lint'].get('errors', '?')} err"
        if not r["lint"]:
            lint_str = "—"

        git_str = "clean" if r["git"].get("uncommitted", 0) == 0 else f"{r['git']['uncommitted']}f"

        print(f"| {r['dir']:20s} | {r['label']:15s} | {tests_str:20s} | {lint_str:10s} | {git_str} |")

    print()
    projects_ok = sum(1 for r in results if r["tests"].get("ok"))
    projects_total = len(results)
    print(f"_总览: {projects_ok}/{projects_total} 项目测试通过"
          f" | {sum(r['lint'].get('ok', False) for r in results)}/{projects_total} lint 通过_")

    # ── Detail: failing projects ──────────────────────
    failing = [r for r in results if not r["tests"].get("ok")]
    if failing:
        print("\n## ⚠️ 未通过项目详情\n")
        for r in failing:
            print(f"### {r['dir']} ({r['label']})")
            out = r["tests"].get("output", "")
            if out:
                print(f"```\n{out}\n```")
            err = r["tests"].get("stderr", "")
            if err:
                print(f"_stderr: {err[:200]}_")
            print()

    # ── Governance entry ──────────────────────────────
    # Write a governance.jsonl entry for this scan
    gov_log = Path.home() / ".hermes/architecture/governance_log/governance.jsonl"
    entry = {
        "action": "health-scan",
        "node_id": "governance-system",
        "status": "ok" if projects_ok == projects_total else "degraded",
        "operator": "cron",
        "detail": f"{projects_ok}/{projects_total} passed, "
                  f"{sum(r['tests'].get('failed', 0) for r in results)} total failures",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(str(gov_log.parent), exist_ok=True)
    with open(str(gov_log), "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    print("_governance heartbeat written_")


if __name__ == "__main__":
    main()
