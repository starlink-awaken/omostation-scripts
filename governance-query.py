#!/usr/bin/env python3
"""
治理度量查询工具

查询 governance-data.json 中的治理数据。
可用于 MCP 工具或命令行查询。

用法:
    python3 scripts/governance-query.py health        # 查询健康度
    python3 scripts/governance-query.py debt          # 查询债务状态
    python3 scripts/governance-query.py trend         # 查询趋势
    python3 scripts/governance-query.py projects      # 查询项目状态
    python3 scripts/governance-query.py all           # 查询所有
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_governance_data() -> dict:
    """加载治理数据"""
    data_path = Path(".omo/_control/governance-data.json")
    if not data_path.exists():
        print("错误: governance-data.json 不存在，请先运行 make governance-data")
        sys.exit(1)
    
    with open(data_path, encoding="utf-8") as f:
        return json.load(f)


def query_health(data: dict):
    """查询健康度"""
    gov = data.get("governance", {})
    print(f"=== 健康度 ===")
    print(f"  health_score: {gov.get('health_score', 0):.1f}")
    print(f"  health_score_raw: {gov.get('health_score_raw', 100):.0f}")
    print(f"  debt_weight: {gov.get('debt_weight', 0):.2f}")
    print(f"  debt_health: {gov.get('debt_health', 0):.1f}")


def query_debt(data: dict):
    """查询债务状态"""
    debt = data.get("debt", {})
    print(f"=== 债务状态 ===")
    print(f"  resolved: {debt.get('resolved_count', 0)}")
    print(f"  unresolved: {debt.get('unresolved_count', 0)}")
    print(f"  total: {debt.get('total_count', 0)}")
    print(f"  resolution_rate: {debt.get('resolution_rate', 0):.1%}")


def query_trend(data: dict):
    """查询趋势"""
    trend = data.get("trend", [])
    print(f"=== 趋势 ===")
    print(f"  {'日期':<12} {'权重':<10} {'健康度':<10}")
    print(f"  {'─'*12} {'─'*10} {'─'*10}")
    for item in trend:
        print(f"  {item.get('date', '-'):<12} {item.get('debt_weight', 0):.2f}{'':<8} {item.get('debt_health', 0):.1f}")


def query_projects(data: dict):
    """查询项目状态"""
    projects = data.get("projects", {})
    print(f"=== 项目状态 ===")
    print(f"  {'项目':<12} {'状态':<10} {'债务数':<10}")
    print(f"  {'─'*12} {'─'*10} {'─'*10}")
    for name, info in projects.items():
        print(f"  {name:<12} {info.get('status', '-'):<10} {info.get('debt_count', 0):<10}")


def query_all(data: dict):
    """查询所有"""
    query_health(data)
    print()
    query_debt(data)
    print()
    query_trend(data)
    print()
    query_projects(data)


def main():
    parser = argparse.ArgumentParser(description="治理度量查询工具")
    parser.add_argument("query", choices=["health", "debt", "trend", "projects", "all"], help="查询类型")
    args = parser.parse_args()
    
    data = load_governance_data()
    
    if args.query == "health":
        query_health(data)
    elif args.query == "debt":
        query_debt(data)
    elif args.query == "trend":
        query_trend(data)
    elif args.query == "projects":
        query_projects(data)
    elif args.query == "all":
        query_all(data)


if __name__ == "__main__":
    main()
