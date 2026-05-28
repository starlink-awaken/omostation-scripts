"""Phase 6X E2E 验证：3 个复杂跨层场景

场景1：资源计量 + 治理报告 (L2 → X1)
场景2：抗熵管线 + 契约验证 (X2 → L1)
场景3：价值堆栈 + 演化引擎 (X3 → X2)
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PASS = 0
FAIL = 0


def log(msg: str, ok: bool = None):
    mark = "✅" if ok else ("❌" if ok is False else "➡️")
    print(f"  {mark} {msg}")


def check(condition: bool, msg: str):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"    ✅ {msg}")
    else:
        FAIL += 1
        print(f"    ❌ {msg}")


def run(cmd: str, cwd: str = None, timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          cwd=cwd, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT ({timeout}s)"
    except FileNotFoundError:
        return -2, "COMMAND NOT FOUND"


def run_script(name: str, args: str = "", timeout: int = 30) -> tuple[int, str]:
    """Run a script respecting its shebang (not via bash)."""
    script = Path.home() / ".hermes" / "scripts" / name
    if not script.exists():
        return -2, f"SCRIPT NOT FOUND: {name}"
    return run(f"{script} {args}", timeout=timeout)


# ═══════════════════════════════════════════════════════════════════════════════
# 场景1：资源计量 → 治理报告 (L2 + X1)
# ═══════════════════════════════════════════════════════════════════════════════

def scenario_1():
    """验证 MCP 调用被记账 → CLI 可查 → 治理脚本可运行。"""
    print(f"\n{'='*50}")
    print(f"  📊 场景1: 资源计量 → 治理报告 (L2→X1)")
    print(f"{'='*50}")

    # 1.1 Accounting 模块导入
    log("验证 accounting 模块...")
    rc, out = run("cd ~/Workspace/agora && python3 -c \"import sys; sys.path.insert(0, 'src'); from agora.accounting import CallRecord, ResourceAccountDB; print('OK')\"")
    check(rc == 0, "accounting 模块可导入")

    # 1.2 写记录 + 查 top
    log("写入3条模拟记录 + 验证查询...")
    # Use a temp script to avoid shell quoting issues
    import tempfile
    acct_script = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp')
    acct_script.write('''
import sys; sys.path.insert(0, "src")
from agora.accounting import CallRecord, ResourceAccountDB
from datetime import datetime, timezone
import os
db_path = "/tmp/phase6x_acct.db"
if os.path.exists(db_path): os.remove(db_path)
db = ResourceAccountDB(db_path)
for caller, svc, inp, out, cost in [
    ("hermes", "minerva.research_now", 5000, 15000, 0.15),
    ("codex", "kos.run_indexer", 2000, 500, 0.003),
    ("hermes", "kos.research_now", 3000, 10000, 0.08),
]:
    db.record_call(CallRecord(caller_id=caller, service_name=svc, tool_name=svc.split(".")[-1],
                   input_tokens=inp, output_tokens=out, cost_usd=cost,
                   billed_to="starlink-core",
                   timestamp=datetime.now(timezone.utc).isoformat()))
top = db.get_top_callers(period="all", limit=5)
report = db.get_report(period="all")
db.close()
print(f"CALLERS:{len(top)}")
print(f"REPORT_CALLS:{report['total_calls']}")
print(f"REPORT_COST:{report['total_cost']}")
''')
    acct_script.close()
    rc, out = run(f"cd ~/Workspace/agora && python3 {acct_script.name}")
    os.unlink(acct_script.name)
    check(rc == 0, f"写入成功: {out.strip()[-50:]}")
    callers = [int(l.split(":")[1]) for l in out.splitlines() if "CALLERS:" in l]
    report_calls = [int(l.split(":")[1]) for l in out.splitlines() if "REPORT_CALLS:" in l]
    check(callers and callers[0] == 2, "top_callers 返回2个caller (hermes+codex)")
    check(report_calls and report_calls[0] == 3, "report 总调用数=3")

    # 1.3 治理脚本
    log("治理脚本可执行性...")
    for script in ["arcnode-weekly-report", "arcnode-drift-alert"]:
        script_path = Path.home() / ".hermes" / "scripts" / script
        check(script_path.exists() and os.access(str(script_path), os.X_OK),
              f"{script} 存在且可执行")

    # 1.4 直接运行 validate-all
    rc, out = run_script("arcnode-validate-all")
    check(rc == 0, f"validate-all 执行成功")
    has_pct = "%" in out
    check(has_pct, "输出含百分比" if has_pct else f"输出: {out[:150]}")


# ═══════════════════════════════════════════════════════════════════════════════
# 场景2：抗熵管线 → 契约验证 (X2 → L1)
# ═══════════════════════════════════════════════════════════════════════════════

def scenario_2():
    """验证 X2 管线各个环节可用 + SSOT 契约验证通过。"""
    print(f"\n{'='*50}")
    print(f"  🔄 场景2: 抗熵管线 → 契约验证 (X2→L1)")
    print(f"{'='*50}")

    # 2.1 X2 管线各脚本存在性
    log("X2 管线脚本完整性...")
    for step in ["freshness-watch", "health-monitor", "dual-baseline", "auto-archive"]:
        sp = Path.home() / ".hermes" / "scripts" / step
        if not sp.exists():
            sp = Path.home() / "Workspace" / "wksp" / "scripts" / step
        check(sp.exists() and os.access(str(sp), os.X_OK), f"{step} 存在")

    # 2.2 X2 管线串联
    log("运行 x2-pipeline-runner...")
    rc, out = run_script("x2-pipeline-runner", timeout=60)
    check(rc == 0, f"管线 exit={rc}")
    for kw, label in [("freshness", "保鲜"), ("health", "健康"), ("baseline", "基线")]:
        check(kw.lower() in out.lower(), f"输出含 {label}")

    # 2.3 SSOT 版本验证 (L1 契约层)
    log("SSOT 版本验证...")
    ssot_dir = Path.home() / "Workspace" / "SSOT" / "tool" / "ssot-kernel"
    ssot_venv = ssot_dir / ".venv"
    py = str(ssot_venv / "bin" / "python") if ssot_venv.exists() else "python3"
    rc, out = run(f"cd {ssot_dir} && {py} -m pytest tests/ -q --tb=line -k version 2>&1", timeout=30)
    check(rc == 0, f"版本测试: {out.strip().split(chr(10))[-1][:60]}")

    # 2.4 演化引擎
    log("arcnode-evolve 演化引擎...")
    rc, out = run_script("arcnode-evolve", "--entropy", timeout=30)
    check(rc == 0, f"evolve exit={rc}")
    has_entropy = "熵" in out or "entropy" in out.lower() or "baseline" in out.lower()
    check(has_entropy, f"输出含熵数据: {out[:100].strip()}")


# ═══════════════════════════════════════════════════════════════════════════════
# 场景3：演化引擎 → 治理闭环 (X2+X3+X1)
# ═══════════════════════════════════════════════════════════════════════════════

def scenario_3():
    """验证治理周报完整、文档齐全、闭合回路。"""
    print(f"\n{'='*50}")
    print(f"  🧬 场景3: 治理闭环 + 文档 (X2+X3+X1)")
    print(f"{'='*50}")

    # 3.1 治理周报
    log("治理周报完整性...")
    rc, out = run_script("arcnode-weekly-report", timeout=30)
    check(rc == 0, f"周报 exit={rc}")
    has_data = "total_entries" in out or "nodes" in out or "📊" in out or "架构" in out
    check(rc == 0, f"周报执行成功 (exit=0)")
    check(len(out) > 100, f"周报有实质内容 ({len(out)}字)")
    check(has_data, "周报含架构数据")

    # 3.2 drfit-alert (silent watchdog)
    log("drift-alert 看门狗...")
    rc, out = run_script("arcnode-drift-alert", timeout=30)
    check(rc == 0, f"drift-alert exit={rc} (静默正常)")

    # 3.3 文档完整性
    log("架构文档完整性...")
    docs_dir = Path.home() / "Documents" / "学习进化" / "基建架构"
    for name, label in [("41-L1-契约版本化策略.md", "L1版本化"), ("42-X3-价值堆栈策略.md", "X3堆栈")]:
        p = docs_dir / name
        check(p.exists(), f"{label} 文档存在")
        if p.exists():
            content = p.read_text(encoding="utf-8")
            check(len(content) > 500, f"{label} 内容完整 ({len(content)}字)")

    # 3.4 X3 文档内容验证
    x3_doc = docs_dir / "42-X3-价值堆栈策略.md"
    if x3_doc.exists():
        content = x3_doc.read_text(encoding="utf-8")
        has_7 = all(kw in content for kw in ["Axiom", "Principle", "Theory", "Framework", "Knowledge", "Skill", "Tool"])
        check(has_7, "X3文档含7个价值层级")
        check("X3↔L1" in content, "含 X3↔L1 集成分析")
        check("X3↔X2" in content, "含 X3↔X2 集成分析")

    # 3.5 跨层一致性 (L1 版本化文档验证 eidos schema 数)
    l1_doc = docs_dir / "41-L1-契约版本化策略.md"
    if l1_doc.exists():
        content = l1_doc.read_text(encoding="utf-8")
        check("identity-role" in content and "v1.0.0" in content, "L1文档含schema版本快照")


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  🧪 Phase 6X E2E 场景验证")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    scenario_1()
    scenario_2()
    scenario_3()

    print(f"\n{'='*50}")
    total = PASS + FAIL
    pct = (PASS / total * 100) if total > 0 else 0
    VERDICT = "🎉 全部通过" if FAIL == 0 else \
              "🟡 基本通过" if FAIL <= 2 else \
              "🟠 需关注" if FAIL <= 5 else "🔴 需修复"
    print(f"  结果: {PASS}/{total} 通过 ({pct:.0f}%)")
    print(f"  判定: {VERDICT}")
    print(f"{'='*50}\n")
    sys.exit(0 if FAIL == 0 else 1)
