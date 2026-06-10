#!/usr/bin/env python3
"""跨组织成本追踪 — Phase 9 / T130

在usage.db基础上加org字段，支持按组织汇总。
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

USAGE_DB = Path.home() / ".kos" / "accounting" / "usage.db"


def _ensure_org_column() -> sqlite3.Connection:
    USAGE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(USAGE_DB))
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
    return conn


def log_call(agent: str, tool: str, cost: float = 0, tokens: int = 0,
             org: str = "starlink-core") -> None:
    conn = _ensure_org_column()
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO resource_usage (caller, service, tokens_input, tokens_output, cost_usd, timestamp, org) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (agent, tool, tokens, 0, cost, ts, org),
    )
    conn.commit()
    conn.close()


def cost_summary_by_org(days: int = 7) -> list[dict]:
    conn = _ensure_org_column()
    rows = conn.execute(
        "SELECT org, COUNT(*) as calls, SUM(cost_usd) as total_cost, SUM(tokens_input) as total_tokens "
        "FROM resource_usage WHERE timestamp > datetime('now', ?) "
        "GROUP BY org ORDER BY total_cost DESC",
        (f'-{days} days',),
    ).fetchall()
    conn.close()
    return [{
        "org": r["org"],
        "calls": r["calls"],
        "cost": round(r["total_cost"] or 0, 4),
        "tokens": r["total_tokens"] or 0,
    } for r in rows]
