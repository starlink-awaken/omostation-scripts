#!/usr/bin/env python3
"""Governance heartbeat — append a timestamp entry to governance.jsonl.

Usage:
    python3 scripts/gov_heartbeat.py

Writes one JSONL entry each run. Designed to be called from governance crons
(arc-conv-gate-verification, omo-gov-heartbeat) so the pipeline never goes silent.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

GOV_LOG = os.path.expanduser("~/.hermes/architecture/governance_log/governance.jsonl")


def heartbeat(status: str = "ok", detail: str = "") -> str:
    """Append a heartbeat entry to governance.jsonl."""
    entry = {
        "action": "heartbeat",
        "node_id": "governance-system",
        "status": status,
        "operator": "cron",
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(os.path.dirname(GOV_LOG), exist_ok=True)
    with open(GOV_LOG, "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry["ts"]


def last_entry_age_hours() -> Optional[float]:
    """Return hours since the last governance log entry."""
    if not os.path.exists(GOV_LOG):
        return None
    with open(GOV_LOG) as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    if not lines:
        return None
    try:
        last = json.loads(lines[-1])
        last_ts = datetime.fromisoformat(last["ts"])
        delta = datetime.now(timezone.utc) - last_ts
        return delta.total_seconds() / 3600
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


if __name__ == "__main__":
    age = last_entry_age_hours()
    detail = f"last_entry_age={age:.1f}h" if age is not None else "no_prior_entries"
    ts = heartbeat(detail=detail)
    print(f"heartbeat_written: {ts} | {detail}")

    # Alert if stale (>48h silence) — this prints to stdout which cron captures
    if age is not None and age > 48:
        print(f"ALERT: Governance pipeline stale — {age:.0f}h since last entry")
    elif age is not None and age > 24:
        print(f"WARN: Governance pipeline aging — {age:.0f}h since last entry")
