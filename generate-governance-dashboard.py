#!/usr/bin/env python3
"""
治理仪表板 HTML 报告生成器

从 .omo/state/system.yaml 和 .omo/_control/debt-dashboard/ 读取数据，
生成可视化的 HTML 报告。

用法:
    python3 scripts/generate-governance-dashboard.py
    python3 scripts/generate-governance-dashboard.py --output governance-report.html
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from lib.bootstrap import workspace_root
from lib.paths import SYSTEM_YAML, OMO_DIR
from lib.yaml_utils import load_yaml


def generate_html(system_data: dict, dashboard_data: dict) -> str:
    """生成 HTML 报告"""
    debt_weight = system_data.get("debt_weight", 0)
    health_score = system_data.get("health_score", 0)
    health_score_raw = system_data.get("health_score_raw", 100)
    
    debt_metrics = system_data.get("debt_metrics", {})
    resolved_count = debt_metrics.get("resolved_count", 0)
    unresolved_count = debt_metrics.get("unresolved_count", 0)
    
    # 健康度颜色
    if health_score >= 90:
        health_color = "#22c55e"
    elif health_score >= 70:
        health_color = "#eab308"
    else:
        health_color = "#ef4444"
    
    # 债务权重颜色
    if debt_weight >= 0.9:
        weight_color = "#22c55e"
    elif debt_weight >= 0.7:
        weight_color = "#eab308"
    else:
        weight_color = "#ef4444"
    
    # 趋势数据
    health_trend = dashboard_data.get("health_trend", [])
    trend_rows = ""
    for item in health_trend:
        trend_rows += f"""
        <tr>
            <td>{item.get('date', '-')}</td>
            <td>{item.get('debt_weight', 0):.2f}</td>
            <td>{item.get('debt_health', 0):.1f}</td>
            <td>{item.get('note', '-')}</td>
        </tr>"""
    
    # 债务分类
    categories = dashboard_data.get("debt_categories", {})
    cat_rows = ""
    for cat_name, cat_data in categories.items():
        cat_rows += f"""
        <tr>
            <td>{cat_name}</td>
            <td>{cat_data.get('resolved', 0)}</td>
            <td>{cat_data.get('partial', 0)}</td>
            <td>{cat_data.get('unresolved', 0)}</td>
        </tr>"""
    
    generated_at = dashboard_data.get("generated_at", datetime.now().isoformat())
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>治理仪表板</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #1e293b; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .subtitle {{ color: #64748b; margin-bottom: 2rem; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }}
        .card {{ background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .card h3 {{ font-size: 0.875rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
        .card .value {{ font-size: 2.5rem; font-weight: 700; }}
        .card .label {{ font-size: 0.875rem; color: #64748b; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f1f5f9; font-weight: 600; font-size: 0.875rem; color: #475569; }}
        .section {{ margin-bottom: 2rem; }}
        .section h2 {{ font-size: 1.25rem; margin-bottom: 1rem; }}
        .status-ok {{ color: #22c55e; }}
        .status-warn {{ color: #eab308; }}
        .status-error {{ color: #ef4444; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>治理仪表板</h1>
        <p class="subtitle">生成时间: {generated_at}</p>
        
        <div class="grid">
            <div class="card">
                <h3>健康度</h3>
                <div class="value" style="color: {health_color}">{health_score:.1f}</div>
                <div class="label">原始分: {health_score_raw:.0f}</div>
            </div>
            <div class="card">
                <h3>债务权重</h3>
                <div class="value" style="color: {weight_color}">{debt_weight:.2f}</div>
                <div class="label">1.0 = 全部解决</div>
            </div>
            <div class="card">
                <h3>已解决</h3>
                <div class="value status-ok">{resolved_count}</div>
                <div class="label">债务项</div>
            </div>
            <div class="card">
                <h3>待解决</h3>
                <div class="value {'status-ok' if unresolved_count == 0 else 'status-warn'}">{unresolved_count}</div>
                <div class="label">债务项</div>
            </div>
        </div>
        
        <div class="section">
            <h2>健康度趋势</h2>
            <table>
                <thead>
                    <tr>
                        <th>日期</th>
                        <th>债务权重</th>
                        <th>健康度</th>
                        <th>变更说明</th>
                    </tr>
                </thead>
                <tbody>
                    {trend_rows}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>债务分类</h2>
            <table>
                <thead>
                    <tr>
                        <th>类别</th>
                        <th>已解决</th>
                        <th>部分解决</th>
                        <th>未解决</th>
                    </tr>
                </thead>
                <tbody>
                    {cat_rows}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""
    
    return html


def main():
    parser = argparse.ArgumentParser(description="生成治理仪表板 HTML 报告")
    parser.add_argument("--output", "-o", default="governance-report.html", help="输出文件路径")
    parser.add_argument("--omo-dir", default=str(OMO_DIR), help=".omo 目录路径")
    args = parser.parse_args()
    
    omo_dir = Path(args.omo_dir)
    
    # 加载数据
    system_path = omo_dir / "state" / "system.yaml"
    dashboard_path = omo_dir / "_control" / "debt-dashboard" / "current.yaml"
    
    if not system_path.exists():
        print(f"错误: {system_path} 不存在")
        sys.exit(1)
    
    system_data = load_yaml(system_path)
    dashboard_data = load_yaml(dashboard_path) if dashboard_path.exists() else {}
    
    # 生成 HTML
    html = generate_html(system_data, dashboard_data)
    
    # 写入文件
    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    
    print(f"✅ 治理仪表板已生成: {output_path}")
    print(f"   健康度: {system_data.get('health_score', 0):.1f}")
    print(f"   债务权重: {system_data.get('debt_weight', 0):.2f}")


if __name__ == "__main__":
    main()
