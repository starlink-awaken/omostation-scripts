#!/usr/bin/env python3
"""跨组织成本追踪 — Phase 9 / T130

在 usage.db 基础上加 org 字段，支持按组织汇总。
逻辑已提取到 lib/cost_tracker.py, 本文件保留为 CLI 入口。
"""

import json

from lib.cost_tracker import CostTracker


def log_call(agent: str, tool: str, cost: float = 0, tokens: int = 0,
             org: str = "starlink-core") -> None:
    tracker = CostTracker()
    tracker.log_call(agent=agent, tool=tool, cost=cost, tokens=tokens, org=org)
    tracker.close()


def cost_summary_by_org(days: int = 7) -> list[dict]:
    tracker = CostTracker()
    result = tracker.summary_by_org(days=days)
    tracker.close()
    return result


if __name__ == "__main__":
    summary = cost_summary_by_org(days=7)
    print(json.dumps(summary, indent=2, ensure_ascii=False))

