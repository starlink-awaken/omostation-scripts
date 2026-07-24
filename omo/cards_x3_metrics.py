"""CARDS X3 value metrics — card_history SQLite 聚合 (P44 R0).

.. deprecated::
    This script has been migrated to omo CLI. Use instead:
        omo audit cards [--db PATH] [--json] [--output PATH]

量化的 X3 value 维度:
- card_count: 当前 card 总量 (按 type/status 分组)
- status_distribution: status 分布 (proposed/active/done/archived)
- mean_age_days: 平均存活时间 (creation → now, 按 type)
- monthly_active: 近 30 天有 history 变更的 card 数

CLI:
    python3 scripts/omo/cards_x3_metrics.py [--db PATH] [--json] [--output PATH]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.bootstrap import workspace_root

WORKSPACE_ROOT = workspace_root()

# 默认 card_history db 路径 (cockpit 数据)
DEFAULT_DB_PATHS = [
    Path.home() / "Documents" / "@驾驶舱" / "data" / "cards" / "cards.db",
    Path.home() / "Documents" / "驾驶舱" / "data" / "cards" / "cards.db",
    Path.home() / ".cards" / "cards.db",
]


def find_card_db() -> Path | None:
    """找第一个存在的 card db"""
    for p in DEFAULT_DB_PATHS:
        if p.exists():
            return p
    # 也检查 cockpit 项目内 (tests fixtures)
    cockpit_db = WORKSPACE_ROOT / "projects" / "cockpit" / "tests" / "fixtures" / "cards.db"
    if cockpit_db.exists():
        return cockpit_db
    return None


def collect_metrics(db_path: Path) -> dict:
    """聚合 card_history 指标"""
    if not db_path.exists():
        return {"error": f"db not found: {db_path}", "stale": 1}

    metrics: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "db_path": str(db_path),
        "card_count": 0,
        "status_distribution": {},
        "type_distribution": {},
        "mean_age_days": 0.0,
        "monthly_active": 0,
    }

    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()

            # 检查表存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            if "cards" not in tables:
                metrics["error"] = "no 'cards' table in db"
                return metrics

            # 总量 + status 分布
            cursor.execute("SELECT status, COUNT(*) FROM cards GROUP BY status")
            metrics["status_distribution"] = dict(cursor.fetchall())

            cursor.execute("SELECT type, COUNT(*) FROM cards GROUP BY type")
            metrics["type_distribution"] = dict(cursor.fetchall())

            cursor.execute("SELECT COUNT(*) FROM cards")
            metrics["card_count"] = cursor.fetchone()[0]

            # 平均 age
            cursor.execute("SELECT created_at FROM cards WHERE created_at IS NOT NULL")
            ages = []
            now = datetime.now(UTC)
            for (created_at,) in cursor.fetchall():
                try:
                    dt = datetime.fromisoformat(created_at)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    ages.append((now - dt).days)
                except (ValueError, AttributeError):
                    continue
            metrics["mean_age_days"] = sum(ages) / len(ages) if ages else 0.0

            # 30 天活跃
            if "card_history" in tables:
                from datetime import timedelta
                cutoff_ts = (now - timedelta(days=30)).isoformat()
                cursor.execute(
                    "SELECT COUNT(DISTINCT card_id) FROM card_history WHERE changed_at >= ?",
                    (cutoff_ts,),
                )
                row = cursor.fetchone()
                metrics["monthly_active"] = row[0] if row else 0

    except sqlite3.Error as e:
        metrics["error"] = f"sqlite error: {e}"
        return metrics

    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="CARDS X3 value metrics")
    parser.add_argument("--db", type=str, help="explicit db path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--output", type=str, help="write to file (relative to workspace)")
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db)
        if not db_path.is_absolute():
            db_path = WORKSPACE_ROOT / db_path
        metrics = collect_metrics(db_path)
    else:
        db_path = find_card_db()
        if not db_path:
            print("⚠️  No card_history db found at standard locations", file=sys.stderr)
            print("   Searched:", [str(p) for p in DEFAULT_DB_PATHS], file=sys.stderr)
            # 不算错误, 标记为 stale
            metrics = {
                "generated_at": datetime.now(UTC).isoformat(),
                "error": "no card db found (cards subsystem may not be initialized)",
                "stale": 1,
                "searched_paths": [str(p) for p in DEFAULT_DB_PATHS],
            }
        else:
            metrics = collect_metrics(db_path)

    if args.json:
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
    else:
        if "error" in metrics:
            print(f"❌ {metrics['error']}")
        else:
            print("=== CARDS X3 value metrics ===")
            print(f"Total cards: {metrics['card_count']}")
            print(f"Status distribution: {metrics['status_distribution']}")
            print(f"Type distribution: {metrics['type_distribution']}")
            print(f"Mean age: {metrics['mean_age_days']:.1f} days")
            print(f"30-day active: {metrics['monthly_active']}")

    if args.output:
        out_path = WORKSPACE_ROOT / args.output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        if not args.json:
            print(f"\n✅ Metrics written to {out_path.relative_to(WORKSPACE_ROOT)}")

    # 退出码: 1 if stale (no db)
    return 1 if metrics.get("stale") or metrics.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())