#!/usr/bin/env python3
"""
plot-metrics.py — 治理债指标趋势图 (纯 ASCII, 无外部依赖)

输入: .omo/_delivery/audit-rollout/ 下所有 <date>-metrics.json 或 <date>.json
字段: drift_count, debt_density, health_grade
输出: metrics-trend.txt (3 张 ASCII bar chart)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from lib.bootstrap import workspace_root, omo_src_path

WORKSPACE_ROOT = workspace_root()
sys.path.insert(0, str(omo_src_path()))

from omo.omo_io import write_text_atomic
from omo.omo_metrics_plot import write_metrics_trend

# ── 路径配置 ──────────────────────────────────────────────
AUDIT_DIR = WORKSPACE_ROOT / ".omo" / "_delivery" / "audit-rollout"
OUTPUT_FILE = AUDIT_DIR / "metrics-trend.txt"

# 健康等级映射 R0-R5 → 数值
HEALTH_MAP = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}


def parse_health(val) -> float:
    """health_grade: R0-R5 → 0-5"""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().upper()
    if s in HEALTH_MAP:
        return float(HEALTH_MAP[s])
    # 容错:纯数字字符串
    try:
        return float(s)
    except ValueError:
        return float("nan")


def load_records() -> list[dict]:
    """扫描 audit-rollout 目录, 收集所有 metrics JSON 文件。

    支持 3 种 JSON 结构:
    1. 顶层直接字段: {drift_count, debt_density, health_grade}
    2. 嵌套 metrics:  {metrics: {drift_count, ...}}
    3. omostation audit-rollout 格式: {repos: {name: {debt_density, health_grade}}, generated_at}
    """
    if not AUDIT_DIR.exists():
        return []
    records = []
    for f in sorted(AUDIT_DIR.iterdir()):
        if f.suffix == ".json" and f.name.startswith("20"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                # 格式 3: omostation audit-rollout (R46 --include-metrics)
                if "repos" in data and "generated_at" in data:
                    for repo_name, repo_data in data.get("repos", {}).items():
                        records.append(
                            {
                                "date": data["generated_at"][:10],
                                "repo": repo_name,
                                "drift_count": repo_data.get("total_drift", 0),
                                "debt_density": float(repo_data.get("debt_density", 0.0)),
                                "health_grade": parse_health(repo_data.get("health_grade", "R0")),
                            }
                        )
                    continue
                # 格式 1 或 2
                inner = data.get("metrics", data)
                records.append(
                    {
                        "date": f.stem[:10],  # 截取 YYYY-MM-DD
                        "drift_count": int(inner.get("drift_count", 0)),
                        "debt_density": float(inner.get("debt_density", 0.0)),
                        "health_grade": parse_health(inner.get("health_grade", "R0")),
                    }
                )
            except Exception:
                pass
    return records


def ascii_bar(val: float, max_val: float, width: int = 40) -> str:
    """生成一条 ASCII bar,满格用█, 空余用 ░"""
    if max_val <= 0:
        ratio = 0.0
    else:
        ratio = min(val / max_val, 1.0)
    filled = int(round(ratio * width))
    return "█" * filled + "░" * (width - filled)


def print_trend_chart(
    title: str, label: str, records: list[dict], key: str, max_val: float
) -> None:
    """打印单张趋势图"""
    print(f"\n{'═' * 56}", file=sys.stdout)
    print(f"  {title}", file=sys.stdout)
    print(f"{'═' * 56}", file=sys.stdout)
    header = f"  {'Date':<12} {'Value':>8}  {'Trend'}"
    print(header, file=sys.stdout)
    print(f"  {'-' * 10} {'-' * 8}  {'-' * 42}", file=sys.stdout)
    for rec in records:
        bar = ascii_bar(rec[key], max_val)
        val_str = f"{rec[key]:.3f}" if key != "drift_count" else f"{rec[key]}"
        print(
            f"  {rec['date']:<12} {val_str:>8}  {bar}",
            file=sys.stdout,
        )


def main() -> None:
    records = load_records()

    #写入文件用 StringIO 中转
    import io

    buf = io.StringIO()

    def out(msg: str):
        buf.write(msg + "\n")

    out("╔══════════════════════════════════════════════════════════╗")
    out("║        织星治理债指标趋势报告 (audit-rollout)         ║")
    out("╚══════════════════════════════════════════════════════════╝")
    out(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out(f"数据源:   {AUDIT_DIR}")

    if not records:
        out("\n  ⚠  No historical data yet — first data point today")
        out("  (目录 .omo/_delivery/audit-rollout/ 中尚无 <date>.json 文件)")
        out("  预期格式: <YYYY-MM-DD>-metrics.json 或 <YYYY-MM-DD>.json")
        out("  必需字段: drift_count, debt_density, health_grade")
        write_metrics_trend(WORKSPACE_ROOT, buf.getvalue())
        print(buf.getvalue())
        return

    out(f"\n  共 {len(records)} 条历史记录")

    # drift_count
    max_drift = max(r["drift_count"] for r in records)
    out_buf = io.StringIO()

    def out2(msg: str):
        out_buf.write(msg + "\n")

    out2("\n" + "═" * 56)
    out2("  Drift Count 趋势 (drift_count vs date)")
    out2("═" * 56)
    out2(f"  {'Date':<12} {'Value':>8}  {'Trend'}")
    out2(f"  {'-' * 10} {'-' * 8}  {'-' * 42}")
    for rec in records:
        bar = ascii_bar(rec["drift_count"], max_drift)
        out2(f"  {rec['date']:<12} {rec['drift_count']:>8}  {bar}")
    out(out_buf.getvalue())

    # debt_density
    max_density = max(r["debt_density"] for r in records)
    out_buf2 = io.StringIO()

    def out3(msg: str):
        out_buf2.write(msg + "\n")

    out3("\n" + "═" * 56)
    out3("  Debt Density 趋势 (debt_density vs date)")
    out3("═" * 56)
    out3(f"  {'Date':<12} {'Value':>8}  {'Trend'}")
    out3(f"  {'-' * 10} {'-' * 8}  {'-' * 42}")
    for rec in records:
        bar = ascii_bar(rec["debt_density"], max_density)
        out3(f"  {rec['date']:<12} {rec['debt_density']:>8.4f}  {bar}")
    out(out_buf2.getvalue())

    # health_grade
    max_health = max(r["health_grade"] for r in records)
    out_buf3 = io.StringIO()

    def out4(msg: str):
        out_buf3.write(msg + "\n")

    out4("\n" + "═" * 56)
    out4("  Health Grade 趋势 (health_grade R0-R5 → 0-5 vs date)")
    out4("═" * 56)
    out4(f"  {'Date':<12} {'Grade':>8}  {'Trend'}")
    out4(f"  {'-' * 10} {'-' * 8}  {'-' * 42}")
    HEALTH_REV = {0: "R0", 1: "R1", 2: "R2", 3: "R3", 4: "R4", 5: "R5"}
    for rec in records:
        bar = ascii_bar(rec["health_grade"], max_health)
        grade_lbl = HEALTH_REV.get(int(rec["health_grade"]), f"R{int(rec['health_grade'])}")
        out4(f"  {rec['date']:<12} {grade_lbl:>8}  {bar}")
    out(out_buf3.getvalue())

    out("\n  评分标准 (R0-R5):")
    out("    R0=优秀(debt_density≤1%)  R1=健康(≤5%)  R2=警告(≤10%)")
    out("    R3=严重(≤30%)  R4=危急(>30%)  R5=失控(>50%)")
    out(f"\n  输出文件: {OUTPUT_FILE}")

    content = buf.getvalue()
    write_metrics_trend(WORKSPACE_ROOT, content)
    print(content)


if __name__ == "__main__":
    main()
