"""cost_tracker.py — SQLite 成本跟踪基础设施。

从 cost_track_org.py 提取, 提供可复用的成本记录和聚合能力。

用法:
    from lib.cost_tracker import CostTracker
    tracker = CostTracker()  # 默认 ~/.kos/accounting/usage.db

    # 记录调用
    tracker.log_call(agent="omo", tool="llm-gateway", cost=0.01, tokens=500, org="starlink-core")

    # 按组织汇总
    summary = tracker.summary_by_org(days=7)
    # [{"org": "starlink-core", "calls": 42, "cost": 0.42, "tokens": 21000}, ...]
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path.home() / ".kos" / "accounting" / "usage.db"


class CostTracker:
    """SQLite-based cost tracker with org dimension.

    Table schema: resource_usage(call_id, caller, service, tokens_input,
    tokens_output, cost_usd, timestamp, org)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """惰性初始化数据库连接 + schema migration。"""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resource_usage (
                    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    caller TEXT NOT NULL,
                    service TEXT NOT NULL,
                    tokens_input INTEGER DEFAULT 0,
                    tokens_output INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    org TEXT DEFAULT 'starlink-core'
                )
            """)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(resource_usage)").fetchall()
            }
            if "org" not in columns:
                conn.execute("ALTER TABLE resource_usage ADD COLUMN org TEXT DEFAULT 'starlink-core'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_org ON resource_usage(org)")
            conn.commit()
            self._conn = conn
        return self._conn

    def log_call(
        self,
        agent: str,
        tool: str,
        cost: float = 0,
        tokens: int = 0,
        org: str = "starlink-core",
    ) -> None:
        """记录一次 API 调用的成本。"""
        ts = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO resource_usage (caller, service, tokens_input, tokens_output, cost_usd, timestamp, org) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (agent, tool, tokens, 0, cost, ts, org),
        )
        self.conn.commit()

    def summary_by_org(self, days: int = 7) -> list[dict[str, Any]]:
        """按组织汇总最近 N 天的成本。"""
        rows = self.conn.execute(
            "SELECT org, COUNT(*) as calls, SUM(cost_usd) as total_cost, SUM(tokens_input) as total_tokens "
            "FROM resource_usage WHERE timestamp > datetime('now', ?) "
            "GROUP BY org ORDER BY total_cost DESC",
            (f"-{days} days",),
        ).fetchall()
        return [
            {
                "org": r["org"],
                "calls": r["calls"],
                "cost": round(r["total_cost"] or 0, 4),
                "tokens": r["total_tokens"] or 0,
            }
            for r in rows
        ]

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> CostTracker:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
