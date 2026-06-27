"""Vault X1 audit — Markdown content hash + author tracking.

Vault 是 Markdown 文档, 无原生审计机制 (X3-value-stack.yaml 标记 implemented: false).
本工具通过 git commit 链路提供 "事实性" 审计: 每个 .md 文件的 content hash
+ 最后修改 author + 时间戳, 作为 X1 audit SSOT.

CLI:
    python3 scripts/omo/vault_x1_audit.py [--days N] [--root PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.bootstrap import workspace_root

WORKSPACE_ROOT = workspace_root()


def git_log_for_file(file_path: Path, days: int = 90) -> dict:
    """获取文件最近 N 天的 git commit 信息"""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%an|%ae|%at|%s", "--", str(file_path.relative_to(WORKSPACE_ROOT))],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        parts = result.stdout.strip().split("|", 4)
        if len(parts) < 5:
            return {}
        sha, author, email, ts, subject = parts
        return {
            "commit": sha,
            "author": author,
            "email": email,
            "timestamp": int(ts),
            "subject": subject,
        }
    except (subprocess.TimeoutExpired, Exception):
        return {}


def content_hash(file_path: Path) -> str:
    """SHA-256 of file content (前 16 chars, 节省空间)"""
    try:
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]
    except (OSError, IOError):
        return "ERROR"


def find_markdown_files(root: Path, exclude_patterns: list[str] | None = None) -> list[Path]:
    """递归找 .md 文件, 排除 .venv / node_modules / .git / .pytest_cache"""
    patterns = exclude_patterns or [
        ".venv", "node_modules", ".git", ".pytest_cache", "__pycache__",
        "_archive", "_archived", "data", "data/", "archive", "snapshot",
        "node_modules", "venv", "dist", "build", ".pytest_cache",
        "htmlcov", "coverage", "site-packages", "__pycache__",
        "node_modules", "outputs", "logs", "cache",
    ]
    result = []
    for md in root.rglob("*.md"):
        if any(p in md.parts for p in patterns):
            continue
        result.append(md)
    return sorted(result)


def audit_vault(root: Path, days: int = 90) -> dict:
    """扫描 root 下所有 .md, 返回审计结果"""
    md_files = find_markdown_files(root)
    cutoff = datetime.now(UTC) - timedelta(days=days)
    results = []
    stale = 0
    no_git = 0
    for md in md_files:
        rel = md.relative_to(WORKSPACE_ROOT)
        git_info = git_log_for_file(md, days)
        file_hash = content_hash(md)
        if not git_info:
            no_git += 1
            results.append({
                "path": str(rel),
                "hash": file_hash,
                "stale": None,
                "no_git": True,
                "age_days": None,
            })
            continue
        ts = datetime.fromtimestamp(git_info["timestamp"], tz=UTC)
        age = datetime.now(UTC) - ts
        is_stale = ts < cutoff
        if is_stale:
            stale += 1
        results.append({
            "path": str(rel),
            "hash": file_hash,
            "stale": is_stale,
            "no_git": False,
            "age_days": age.days,
            "last_author": git_info["author"],
            "last_commit": git_info["commit"][:8],
            "last_subject": git_info["subject"][:60],
        })
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "days_threshold": days,
        "total_files": len(md_files),
        "stale_files": stale,
        "no_git_files": no_git,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Vault X1 audit — Markdown content hash + author")
    parser.add_argument("--days", type=int, default=90, help="staleness threshold in days")
    parser.add_argument("--root", type=str, default=str(WORKSPACE_ROOT),
                        help="root to scan (default: workspace root)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--output", type=str, help="write to file (relative to workspace)")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_absolute():
        root = WORKSPACE_ROOT / root

    audit = audit_vault(root, args.days)

    if args.json:
        print(json.dumps(audit, indent=2, ensure_ascii=False))
    else:
        print(f"=== Vault X1 audit (stale > {args.days} days) ===")
        print(f"Total .md files: {audit['total_files']}")
        print(f"Stale: {audit['stale_files']}")
        print(f"No git history: {audit['no_git_files']}")
        print()
        # 列出 stale 的 (按 age 降序)
        stale_list = sorted(
            [r for r in audit["results"] if r.get("stale") is True],
            key=lambda x: x.get("age_days", 0),
            reverse=True,
        )
        for r in stale_list[:20]:
            print(f"  {r['age_days']:>4}d  {r['last_author']:<20}  {r['path']}")
        if len(stale_list) > 20:
            print(f"  ... ({len(stale_list) - 20} more)")

    if args.output:
        out_path = WORKSPACE_ROOT / args.output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
        if not args.json:
            print(f"\n✅ Full audit written to {out_path.relative_to(WORKSPACE_ROOT)}")

    # 退出码: 有 stale 警告 = 1
    return 1 if audit["stale_files"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())