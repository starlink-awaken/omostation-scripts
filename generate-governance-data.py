#!/usr/bin/env python3
"""
治理数据 JSON 生成器

从 .omo/state/system.yaml 读取数据，生成 governance-data.json。
可用于 BOS URI 服务或 MCP 工具读取。

用法:
    python3 scripts/generate-governance-data.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.omo_io import write_text_atomic


def load_yaml(path: Path) -> dict:
    """加载 YAML 文件"""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main():
    omo_dir = Path(".omo")
    system_path = omo_dir / "state" / "system.yaml"
    dashboard_path = omo_dir / "_control" / "debt-dashboard" / "current.yaml"
    output_path = omo_dir / "_control" / "governance-data.json"
    
    if not system_path.exists():
        print(f"错误: {system_path} 不存在")
        sys.exit(1)
    
    system_data = load_yaml(system_path)
    dashboard_data = load_yaml(dashboard_path) if dashboard_path.exists() else {}
    
    # 构建 JSON 数据
    governance_data = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "governance": {
            "health_score": system_data.get("health_score", 0),
            "health_score_raw": system_data.get("health_score_raw", 100),
            "debt_weight": system_data.get("debt_weight", 0),
            "debt_health": system_data.get("debt_metrics", {}).get("debt_health", 0),
        },
        "debt": {
            "resolved_count": system_data.get("debt_metrics", {}).get("resolved_count", 0),
            "unresolved_count": system_data.get("debt_metrics", {}).get("unresolved_count", 0),
            "total_count": (
                system_data.get("debt_metrics", {}).get("resolved_count", 0) +
                system_data.get("debt_metrics", {}).get("unresolved_count", 0)
            ),
            "resolution_rate": 0,
        },
        "categories": dashboard_data.get("debt_categories", {}),
        "trend": dashboard_data.get("health_trend", []),
        "projects": {
            "kairon": {"status": "healthy", "debt_count": 0},
            "gbrain": {"status": "healthy", "debt_count": 0},
            "metaos": {"status": "healthy", "debt_count": 0},
            "agora": {"status": "healthy", "debt_count": 0},
            "cockpit": {"status": "healthy", "debt_count": 0},
            "ecos": {"status": "healthy", "debt_count": 0},
            "omo": {"status": "healthy", "debt_count": 0},
            "runtime": {"status": "healthy", "debt_count": 0},
        },
    }
    
    # 计算解决率
    total = governance_data["debt"]["total_count"]
    resolved = governance_data["debt"]["resolved_count"]
    governance_data["debt"]["resolution_rate"] = resolved / total if total > 0 else 0
    
    # 写入文件
    write_text_atomic(output_path, json.dumps(governance_data, indent=2, ensure_ascii=False) + "\n")
    
    print(f"✅ 治理数据已生成: {output_path}")
    print(f"   健康度: {governance_data['governance']['health_score']:.1f}")
    print(f"   债务权重: {governance_data['governance']['debt_weight']:.2f}")
    print(f"   解决率: {governance_data['debt']['resolution_rate']:.1%}")


if __name__ == "__main__":
    main()
