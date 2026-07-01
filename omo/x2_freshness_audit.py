"""
X2 Freshness Audit Runner — P43 R7 闭环触发器

执行 .omo/_truth/x2-freshness-rules.yaml 中定义的 3 条 P43 巡检规则:
- X2-FRESH-DEBT-EVIDENCE-INTEGRITY: 14 天巡检 debt evidence 完整性
- X2-FRESH-CROSS-PROJECT-LINT: 7 天巡检全子项目 ruff
- X2-FRESH-MOF-VERSION-BUMP: 30 天巡检 MOF 版本

cron 调用:
  0 9 * * 1   # 每周一 9:00
  INVOCATION_ID=cron OPC_TRIGGER=freshness-audit \
    uv run python scripts/omo/x2_freshness_audit.py

输出: .omo/_delivery/freshness-audit/YYYY-MM-DD.json
退出码: 0 (全 OK) / 1 (有 stale warning) / 2 (有 escalated)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.bootstrap import workspace_root
from lib.paths import OMO_DIR
from lib.yaml_utils import load_yaml_or_default

WORKSPACE_ROOT = workspace_root()
DELIVERY_DIR = OMO_DIR / "_delivery" / "freshness-audit"


def _resolve_truth_dir():
    """运行时解析 TRUTH_DIR (允许测试 monkeypatch OMO_DIR)"""
    return OMO_DIR / "_truth"


def _resolve_debt_dir():
    return OMO_DIR / "debt" / "items"


def check_debt_evidence() -> dict:
    """X2-FRESH-DEBT-EVIDENCE-INTEGRITY — 14 天巡检"""
    debt_dir = _resolve_debt_dir()
    if not debt_dir.exists():
        return {"rule_id": "X2-FRESH-DEBT-EVIDENCE-INTEGRITY", "status": "ok",
                "stale": 0, "total": 0, "details": "no debt items"}

    stale = []
    total = 0
    for yaml_file in debt_dir.glob("*.yaml"):
        total += 1
        try:
            data = load_yaml_or_default(yaml_file, {})
        except Exception:
            continue
        state = data.get("lifecycle_state", "unknown")
        if state == "closed":
            evidence = data.get("resolution_evidence", "")
            if not evidence or len(str(evidence)) < 20:
                stale.append({
                    "id": data.get("id", yaml_file.stem),
                    "issue": f"closed without resolution_evidence ≥ 20 chars (got {len(str(evidence))})",
                })
        elif state == "deferred":
            if not data.get("next_review_at") or not data.get("gate_level"):
                stale.append({
                    "id": data.get("id", yaml_file.stem),
                    "issue": "deferred without next_review_at + gate_level",
                })
    status = "ok" if not stale else "warning"
    return {"rule_id": "X2-FRESH-DEBT-EVIDENCE-INTEGRITY", "status": status,
            "stale": len(stale), "total": total, "details": stale[:10]}


def check_cross_project_lint() -> dict:
    """X2-FRESH-CROSS-PROJECT-LINT — 7 天巡检"""
    subprojects = ["kairon", "cockpit", "runtime", "omo", "metaos", "aetherforge", "c2g", "ecos"]
    stale = []
    for proj in subprojects:
        proj_root = WORKSPACE_ROOT / "projects" / proj
        proj_src = proj_root / "src" / proj
        paths_to_check: list[str] = []
        if proj_src.exists():
            paths_to_check.append(str(proj_src))
        # monorepo 布局: kairon/ecos/aetherforge 同时有 packages/ 子项目
        extra = proj_root / "packages"
        if extra.exists():
            for pkg_dir in extra.iterdir():
                if pkg_dir.is_dir() and (pkg_dir / "pyproject.toml").exists():
                    paths_to_check.append(str(pkg_dir))
        # _legacy/ 是已归档代码 (llm-gateway → aetherforge), 跳过
        exclude_args: list[str] = []
        if (proj_root / "packages" / "gateway" / "src" / "llm_gateway" / "_legacy").exists():
            exclude_args.append("--exclude=packages/gateway/src/llm_gateway/_legacy")
        if not paths_to_check:
            continue
        try:
            result = subprocess.run(
                ["uv", "run", "ruff", "check", *paths_to_check, "--statistics", *exclude_args],
                cwd=str(proj_root),
                capture_output=True, text=True, timeout=120,
            )
            output = result.stdout + result.stderr
            import re
            # E902 (No such file or directory) 当 paths_to_check 包含不存在的目录时触发,
            # 这些不算真实 lint 错误. 解析时跳过 E902 行.
            filtered_output = "\n".join(
                line for line in output.splitlines()
                if not re.match(r"^\s*E902\b", line)
                and "Failed to lint" not in line
            )
            m = re.search(r"Found\s+(\d+)\s+errors?", filtered_output)
            errors = int(m.group(1)) if m else 0
            if errors > 0:
                stale.append({"project": proj, "errors": errors})
        except subprocess.TimeoutExpired:
            stale.append({"project": proj, "errors": "TIMEOUT"})
        except Exception as e:
            stale.append({"project": proj, "errors": f"ERROR: {e}"})
    status = "ok" if not stale else "warning"
    return {"rule_id": "X2-FRESH-CROSS-PROJECT-LINT", "status": status,
            "stale": len(stale), "total": len(subprojects), "details": stale}


def check_mof_version_bump() -> dict:
    """X2-FRESH-MOF-VERSION-BUMP — 30 天巡检"""
    version_file = _resolve_truth_dir() / "mof-version.yaml"
    if not version_file.exists():
        return {"rule_id": "X2-FRESH-MOF-VERSION-BUMP", "status": "warning",
                "stale": 1, "total": 0, "details": "mof-version.yaml missing"}
    try:
        data = load_yaml_or_default(version_file, {})
        history = data.get("history", [])
        if not history:
            return {"rule_id": "X2-FRESH-MOF-VERSION-BUMP", "status": "warning",
                    "stale": 1, "total": 0, "details": "no history"}
        latest = history[-1]
        latest_ts = latest.get("timestamp", "")
        if not latest_ts:
            return {"rule_id": "X2-FRESH-MOF-VERSION-BUMP", "status": "warning",
                    "stale": 1, "total": 0, "details": "no timestamp"}
        ts = latest_ts.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            return {"rule_id": "X2-FRESH-MOF-VERSION-BUMP", "status": "warning",
                    "stale": 1, "total": 0, "details": f"unparseable timestamp: {latest_ts}"}
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - dt).days
        status = "ok" if age_days <= 30 else "warning"
        return {"rule_id": "X2-FRESH-MOF-VERSION-BUMP", "status": status,
                "stale": 0 if status == "ok" else 1, "total": len(history),
                "details": f"latest bump {age_days} days ago (v{data.get('version', '?')})"}
    except Exception as e:
        return {"rule_id": "X2-FRESH-MOF-VERSION-BUMP", "status": "warning",
                "stale": 1, "total": 0, "details": f"parse error: {e}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="X2 freshness audit runner")
    parser.add_argument("--dry-run", action="store_true", help="don't write audit log")
    parser.add_argument("--only", type=str, help="only run specified rule_id")
    args = parser.parse_args()

    checks: list = [
        check_debt_evidence,
        check_cross_project_lint,
        check_mof_version_bump,
    ]
    if args.only:
        checks = [c for c in checks if c.__name__ == args.only]

    results = []
    for check_fn in checks:
        print(f"⏳ {check_fn.__name__}...")
        try:
            results.append(check_fn())
            r = results[-1]
            print(f"   {r['rule_id']}: {r['status'].upper()} ({r['stale']}/{r['total']} stale)")
        except Exception as e:
            results.append({"rule_id": check_fn.__name__, "status": "error", "details": str(e)})
            print(f"   {check_fn.__name__}: ERROR ({e})")

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "invocation_id": "cron",
        "opc_trigger": "freshness-audit",
        "rules_total": len(results),
        "rules_ok": sum(1 for r in results if r["status"] == "ok"),
        "rules_warning": sum(1 for r in results if r["status"] == "warning"),
        "rules_error": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }

    if not args.dry_run:
        DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
        date_slug = datetime.now(UTC).strftime("%Y-%m-%d")
        out_file = DELIVERY_DIR / f"{date_slug}.json"
        out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n✅ Audit written to {out_file.relative_to(WORKSPACE_ROOT)}")

    if summary["rules_error"] > 0:
        return 2
    if summary["rules_warning"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())