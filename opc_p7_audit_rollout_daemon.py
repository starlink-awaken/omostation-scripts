#!/usr/bin/env python3
"""OPC P7 audit rollout daemon — 跨仓 audit rollout 定时化.

P7-H3: E2 dispatcher cron (monthly + weekly + pre-release) + 5 仓 §17 metrics 聚合.

设计:
  - 入口: omo cli `audit-rollout` (primary)
  - fallback: `scripts/opc_audit_rollout_5repos.py` (5 仓聚合库函数, baseline 缺失时也可跑通)
  - 模式: weekly (default) / monthly / pre-release (env OPC_MODE)
  - 仓储: 5 仓 (workspace / omo / llm-gateway / compute-mesh / runtime)
  - 输出: .omo/_delivery/audit-rollout/{date}-{mode}.json
        + .omo/_control/evolution/drift-history/{date}.json
  - cron: scripts/opc_p7_audit_rollout_cron.sh (供 launchd / cron 调用)
  - 触发源: OPC_TRIGGER 环境变量 (cron / manual), 由 wrapper 注入
  - 写回语义:
      * 每次跑都写 .omo/_delivery/audit-rollout/index.json (无论成败)
      * run entry 含 4 字段: returncode / fallback_used / trigger_source / primary_error
      * primary 成功 (rc=0) → fallback_used=false, output_path=primary
      * primary 失败 + fallback 成功 → fallback_used=true, output_path=fallback
      * primary 失败 + fallback 失败 → fallback_used=false, returncode=primary, output_path=None
        (仍写 index, 不再静默跳过; 索引语义"我们至少记录了这次失败")
      * primary 成功但产物 parse fail → returncode=primary, output_path=None
        (仍写 index, 记录产物异常)

红线: cross-repo metrics 仅有规划无消费 = 禁止.  本脚本确保 metrics
      落盘 + drift-history 写历史 + index 持续可写.

并发: _update_history_index 走 fcntl.flock (LOCK_EX) 防 race condition,
      N 并行跑 N 条 entry 全部落盘 (无覆盖丢失).
      锁文件: .omo/_delivery/audit-rollout/index.json.lock

返回值:
  - primary 成功 → 0
  - primary 失败 + fallback 成功 → 0
  - primary 失败 + fallback 失败 → 1
  - primary 成功 + 产物异常 → 1
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


REPOS = [
    ("workspace", "."),
    ("omo", "projects/omo"),
    ("llm-gateway", "projects/llm-gateway"),
    ("compute-mesh", "projects/compute-mesh"),
    ("runtime", "projects/runtime"),
]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _trigger_source() -> str:
    val = os.environ.get("OPC_TRIGGER", "manual")
    return val if val in ("manual", "cron") else "manual"


def _history_index_path() -> Path:
    return ROOT / ".omo" / "_delivery" / "audit-rollout" / "index.json"


def _run_primary_audit_rollout(mode: str) -> dict[str, Any]:
    """调 omo cli audit-rollout, 5 仓聚合 (primary 入口)."""
    repos_args: list[str] = []
    for name, rel in REPOS:
        repos_args += ["--repos", f"{name}:{rel}"]
    out_dir = ROOT / ".omo" / "_delivery" / "audit-rollout"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_today()}-{mode}.json"

    cmd = [
        "python3",
        "-m",
        "omo.cli",
        "audit-rollout",
        *repos_args,
        "--include-metrics",
        "--output",
        str(out_path),
    ]
    env = {**os.environ, "PYTHONPATH": str(ROOT / "projects" / "omo" / "src")}
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env)
    primary = {
        "returncode": result.returncode,
        "stdout_tail": result.stdout.strip().splitlines()[-5:],
        "stderr_tail": result.stderr.strip().splitlines()[-5:],
        "output_path": str(out_path.relative_to(ROOT)) if out_path.exists() else None,
    }
    if result.returncode == 0 and out_path.exists():
        try:
            primary["payload"] = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            primary["payload"] = {"error": "parse fail"}
    return primary


def _run_fallback_5repos() -> dict[str, Any]:
    """fallback: scripts/opc_audit_rollout_5repos.py 库函数直调, baseline 缺失可跑通.

    fallback 自身产物: .omo/_delivery/audit-rollout/{date}-5repos.json
    fallback 阶段: 同时 copy 5repos.json → {date}-{mode}.json (与 primary 同名),
                    让 mode-specific 输出 (weekly/monthly/pre-release) 一致存在,
                    满足 P7-H3 acceptance: "fallback 成功时必须写 mode-specific 输出".
    """
    result = subprocess.run(
        [sys.executable, "scripts/opc_audit_rollout_5repos.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    fallback_path = ROOT / ".omo" / "_delivery" / "audit-rollout" / f"{_today()}-5repos.json"
    mode_specific_path = ROOT / ".omo" / "_delivery" / "audit-rollout" / f"{_today()}-weekly.json"
    payload = None
    if fallback_path.exists():
        try:
            payload = json.loads(fallback_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"error": "parse fail"}
    return {
        "returncode": result.returncode,
        "stdout_tail": result.stdout.strip().splitlines()[-5:],
        "stderr_tail": result.stderr.strip().splitlines()[-5:],
        "output_path": str(fallback_path.relative_to(ROOT)) if fallback_path.exists() else None,
        "payload": payload,
    }


def _run_audit_rollout(mode: str) -> dict[str, Any]:
    """三态 run: primary_ok / fallback_ok / failed.

    写回 schema:
      {
        "mode": str,
        "returncode": int,  # 0 表示 overall success (primary 或 fallback 之一成功)
        "fallback_used": bool,
        "primary_returncode": int,
        "fallback_returncode": int | None,
        "output_path": str | None,
        "primary_output_path": str | None,
        "fallback_output_path": str | None,
        "primary_error": str | None,  # primary returncode != 0 时附 stderr tail
        "payload": dict | None,
      }

    mode-specific 输出契约:
      primary_ok → output_path = {date}-{mode}.json (cli 直接产生)
      fallback_ok → 同步把 5repos.json 内容复制到 {date}-{mode}.json,
                    让 wrapper 无论 primary/fallback 哪种路径, mode-specific 文件
                    (weekly/monthly/pre-release) 都存在 (P7-H3 验收要求).
                    output_path 仍指向 5repos.json (原始 fallback 产物),
                    primary_output_path 指向 5repos 已被 copy 的 {date}-{mode}.json
                    实际副本 (含 5repos payload).
    """
    primary = _run_primary_audit_rollout(mode)
    primary_ok = primary["returncode"] == 0 and primary.get("output_path") is not None

    if primary_ok:
        return {
            "mode": mode,
            "returncode": 0,
            "fallback_used": False,
            "primary_returncode": primary["returncode"],
            "fallback_returncode": None,
            "output_path": primary["output_path"],
            "primary_output_path": primary["output_path"],
            "fallback_output_path": None,
            "primary_error": None,
            "payload": primary.get("payload"),
        }

    # primary failed → 走 fallback
    fallback = _run_fallback_5repos()
    fallback_ok = fallback["returncode"] == 0 and fallback.get("output_path") is not None

    if fallback_ok:
        # 同步 copy 5repos.json → {date}-{mode}.json (P7-H3 acceptance)
        mode_specific_path = ROOT / ".omo" / "_delivery" / "audit-rollout" / f"{_today()}-{mode}.json"
        try:
            payload_data = fallback.get("payload") or {}
            mode_specific_path.write_text(
                json.dumps(payload_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            mode_specific_rel = str(mode_specific_path.relative_to(ROOT))
        except (OSError, TypeError):
            mode_specific_rel = None
        return {
            "mode": mode,
            "returncode": 0,
            "fallback_used": True,
            "primary_returncode": primary["returncode"],
            "fallback_returncode": fallback["returncode"],
            "output_path": fallback["output_path"],
            "primary_output_path": mode_specific_rel,
            "fallback_output_path": fallback["output_path"],
            "primary_error": (primary["stderr_tail"][-1] if primary["stderr_tail"] else f"rc={primary['returncode']}"),
            "payload": fallback.get("payload"),
        }

    # primary + fallback 都失败 → 仍写回, 标 failed
    return {
        "mode": mode,
        "returncode": 1,
        "fallback_used": True,
        "primary_returncode": primary["returncode"],
        "fallback_returncode": fallback["returncode"],
        "output_path": None,
        "primary_output_path": primary["output_path"],
        "fallback_output_path": fallback["output_path"],
        "primary_error": (primary["stderr_tail"][-1] if primary["stderr_tail"] else f"rc={primary['returncode']}"),
        "fallback_error": (fallback["stderr_tail"][-1] if fallback["stderr_tail"] else f"rc={fallback['returncode']}"),
        "payload": fallback.get("payload") or primary.get("payload"),
    }


def _write_drift_history(mode: str, rollout: dict[str, Any]) -> Path:
    out_dir = ROOT / ".omo" / "_control" / "evolution" / "drift-history"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_today()}.json"
    summary = {
        "generated_at": _now_iso(),
        "mode": mode,
        "rollout": {
            "returncode": rollout.get("returncode"),
            "fallback_used": rollout.get("fallback_used"),
            "output_path": rollout.get("output_path"),
        },
    }
    payload = rollout.get("payload")
    if isinstance(payload, dict) and "repos" in payload:
        repos = payload["repos"]
        summary["per_repo"] = {
            name: {
                "health_grade": data.get("health_grade"),
                "drift": data.get("total_drift"),
                "records": data.get("total_records"),
            }
            for name, data in repos.items()
        }
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def _load_history_index() -> dict[str, Any]:
    path = _history_index_path()
    if not path.exists():
        return {"runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": []}


def _update_history_index(mode: str, rollout: dict[str, Any], history_path: Path) -> dict[str, Any]:
    """index 写回 (LOCK_EX 防 race).

    N 并行跑 N 条 entry 全部落盘 (无覆盖丢失):
      1. open 锁文件 (LOCK_EX)
      2. _load_history_index (此时其他进程阻塞)
      3. append new run entry
      4. write index.json
      5. close 锁文件 (LOCK_UN 自动)

    锁文件路径: index_path + ".lock" (与 index 同目录, 不污染 .omo 状态)
    """
    path = _history_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    lock_handle = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            # load (在锁内, 避免 read-modify-write race)
            if path.exists():
                try:
                    index = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    index = {"runs": []}
            else:
                index = {"runs": []}
            runs = index.setdefault("runs", [])
            payload = rollout.get("payload") if isinstance(rollout.get("payload"), dict) else {}
            repos = payload.get("repos", {}) if isinstance(payload, dict) else {}
            run_entry: dict[str, Any] = {
                "generated_at": _now_iso(),
                "day": _today(),
                "mode": mode,
                "trigger_source": _trigger_source(),
                "returncode": rollout.get("returncode"),
                "fallback_used": rollout.get("fallback_used"),
                "primary_returncode": rollout.get("primary_returncode"),
                "fallback_returncode": rollout.get("fallback_returncode"),
                "output_path": rollout.get("output_path"),
                "primary_output_path": rollout.get("primary_output_path"),
                "fallback_output_path": rollout.get("fallback_output_path"),
                "primary_error": rollout.get("primary_error"),
                "repo_count": len(repos) if isinstance(repos, dict) else 0,
                "history_path": str(history_path.relative_to(ROOT)),
            }
            if rollout.get("fallback_error"):
                run_entry["fallback_error"] = rollout["fallback_error"]
            runs.append(run_entry)
            runs.sort(key=lambda item: str(item.get("generated_at", "")))
            index["runs"] = runs
            index["summary"] = {
                "run_count": len(runs),
                "weekly_runs": sum(1 for item in runs if item.get("mode") == "weekly"),
                "monthly_runs": sum(1 for item in runs if item.get("mode") == "monthly"),
                "pre_release_runs": sum(1 for item in runs if item.get("mode") == "pre-release"),
                "cron_run_count": sum(1 for item in runs if item.get("trigger_source") == "cron"),
                "manual_run_count": sum(1 for item in runs if item.get("trigger_source") == "manual"),
                "fallback_used_count": sum(1 for item in runs if item.get("fallback_used")),
                "failed_count": sum(1 for item in runs if item.get("returncode") not in (0, None)),
                "latest_output_path": runs[-1]["output_path"] if runs else None,
                "latest_trigger_source": runs[-1]["trigger_source"] if runs else None,
            }
            # 写回 (在锁内, 原子 write 对其他进程不可见中间态)
            path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    finally:
        lock_handle.close()
    return index


def main() -> int:
    mode = os.environ.get("OPC_MODE", "weekly")
    rollout = _run_audit_rollout(mode)
    history_path = _write_drift_history(mode, rollout)
    history_index = _update_history_index(mode, rollout, history_path)
    summary = {
        "generated_at": _now_iso(),
        "mode": mode,
        "trigger_source": _trigger_source(),
        "rollout_returncode": rollout.get("returncode"),
        "fallback_used": rollout.get("fallback_used"),
        "rollout_output_path": rollout.get("output_path"),
        "primary_returncode": rollout.get("primary_returncode"),
        "fallback_returncode": rollout.get("fallback_returncode"),
        "drift_history": str(history_path.relative_to(ROOT)),
        "history_index": str(_history_index_path().relative_to(ROOT)),
        "history_summary": history_index.get("summary", {}),
    }
    out_dir = ROOT / ".omo" / "_delivery" / "audit-rollout"
    summary_path = out_dir / f"{_today()}-{mode}-daemon-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"# mode: {mode}", file=sys.stderr)
    print(f"# trigger_source: {_trigger_source()}", file=sys.stderr)
    print(f"# rollout rc: {rollout.get('returncode')}", file=sys.stderr)
    print(f"# fallback_used: {rollout.get('fallback_used')}", file=sys.stderr)
    print(f"# output: {rollout.get('output_path')}", file=sys.stderr)
    print(f"# drift history: {history_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"# history index: {_history_index_path().relative_to(ROOT)}", file=sys.stderr)
    print(f"# summary: {summary_path.relative_to(ROOT)}", file=sys.stderr)
    return rollout.get("returncode", 1)


if __name__ == "__main__":
    raise SystemExit(main())
