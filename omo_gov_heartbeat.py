#!/usr/bin/env python3
"""omo-gov-heartbeat — 治理管道心跳检测

检查治理管道的各项指标是否健康。
用于 cron job 定时执行，governance.jsonl 超过 48h 无新条目时报警。

检查项:
  1. governance.jsonl 最新条目时效（阈值：48h）
  2. 治理 cron jobs 是否全部注册（阈值：>=7）
  3. APPENDIX: system.yaml 健康分

输出格式:
  JSON 单行，含 status/info/warnings/errors
  全部健康时输出空（cron 静默模式）
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

from lib.paths import SYSTEM_YAML
from lib.yaml_utils import load_yaml

GOV_LOG = Path.home() / ".hermes" / "architecture" / "governance_log" / "governance.jsonl"
MAX_GOV_AGE_HOURS = 48
MIN_CRON_JOBS = 7


def check_govlog_age() -> dict:
    """检查 governance.jsonl 最新条目是否过期"""
    if not GOV_LOG.exists():
        return {"status": "error", "msg": f"governance.jsonl not found: {GOV_LOG}"}

    lines = GOV_LOG.read_text().strip().split("\n")
    if not lines:
        return {"status": "warning", "msg": "governance.jsonl is empty"}

    last_str = lines[-1]
    try:
        last = json.loads(last_str)
    except json.JSONDecodeError:
        return {"status": "error", "msg": "governance.jsonl: malformed last entry"}

    ts_str = last.get("ts", "")
    if not ts_str:
        return {"status": "warning", "msg": "governance.jsonl: last entry has no ts"}

    try:
        last_ts = datetime.fromisoformat(ts_str)
        age_hours = (datetime.now(UTC) - last_ts).total_seconds() / 3600
    except (ValueError, TypeError):
        return {"status": "error", "msg": f"governance.jsonl: unparseable ts: {ts_str}"}

    if age_hours > MAX_GOV_AGE_HOURS:
        return {
            "status": "error",
            "msg": f"governance.jsonl stale: last entry {age_hours:.0f}h ago (>{MAX_GOV_AGE_HOURS}h)",
            "age_hours": round(age_hours, 1),
            "last_action": last.get("action", "?"),
        }

    return {"status": "ok", "age_hours": round(age_hours, 1)}


def check_cron_jobs() -> dict:
    """检查 Hermes cron jobs 数量"""
    try:
        # 使用 cronjob action=list 通过 subprocess 调用
        r = subprocess.run(
            [sys.executable, "-m", "cronjob", "action=list"],
            capture_output=True, text=True, timeout=30,
        )
        output = r.stdout + r.stderr
        count = 0
        for line in output.split("\n"):
            if '"schedule"' in line or '"name"' in line:
                continue
            if '"enabled"' in line:
                count += 1
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        return {"status": "error", "msg": f"cron list failed: {e}"}

    if count < MIN_CRON_JOBS:
        return {
            "status": "warning",
            "msg": f"Only {count} cron jobs found (< {MIN_CRON_JOBS})",
            "count": count,
        }

    return {"status": "ok", "count": count}


def check_health_score() -> dict:
    """检查 system.yaml 健康分"""
    if not SYSTEM_YAML.exists():
        return {"status": "warning", "msg": "system.yaml not found"}

    try:
        data = load_yaml(SYSTEM_YAML)
        score = data.get("health_score", "?")
        return {"status": "ok", "health_score": score}
    except Exception as e:
        return {"status": "warning", "msg": f"system.yaml read failed: {e}"}


def main() -> int:
    checks = {
        "govlog_age": check_govlog_age(),
        "cron_jobs": check_cron_jobs(),
        "health_score": check_health_score(),
    }

    errors = [k for k, v in checks.items() if v.get("status") == "error"]
    warnings = [k for k, v in checks.items() if v.get("status") == "warning"]

    report = {
        "ts": datetime.now(UTC).isoformat(),
        "checks": checks,
        "healthy": len(errors) == 0,
    }

    if errors:
        report["errors"] = errors
        print(json.dumps(report, ensure_ascii=False))
        return 0 if not errors else 0  # 不退出码报错，让 cron 判断

    if warnings:
        report["warnings"] = warnings
        print(json.dumps(report, ensure_ascii=False))
        return 0

    # 全健康 → 静默
    return 0


if __name__ == "__main__":
    sys.exit(main())
