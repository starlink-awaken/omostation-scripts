#!/usr/bin/env python3
"""
治理数据 JSON 生成器

从 .omo/state/system.yaml 读取数据，生成 governance-data.json。
可用于 BOS URI 服务或 MCP 工具读取。

用法:
    python3 scripts/generate-governance-data.py
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.omo_governance_data import build_governance_data, write_governance_data


def main():
    try:
        governance_data = build_governance_data(ROOT)
    except FileNotFoundError as exc:
        print(f"错误: {exc}")
        return 1
    output_path = write_governance_data(ROOT, governance_data)
    print(f"✅ 治理数据已生成: {output_path}")
    print(f"   健康度: {governance_data['governance']['health_score']:.1f}")
    print(f"   债务权重: {governance_data['governance']['debt_weight']:.2f}")
    print(f"   解决率: {governance_data['debt']['resolution_rate']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
