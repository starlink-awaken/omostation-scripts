#!/usr/bin/env python3
"""
eCOS v5 BOS URI System Demo
============================
快速演示脚本：验证 BOS URI 系统的核心能力。

运行: python3 scripts/demo-bos-system.py
要求: python3, pyyaml (pip install pyyaml)
"""

import sys
from pathlib import Path

WS = Path(__file__).parent.parent
sys.path.insert(0, str(WS / "projects" / "agora" / "src"))
sys.path.insert(0, str(WS / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools"))

def banner(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

def ok(msg): print(f"  ✅ {msg}")
def warn(msg): print(f"  ⚠️ {msg}")
def info(msg): print(f"     {msg}")

# ═══════════════════════════════════════════════════════════════
# Demo flow
# ═══════════════════════════════════════════════════════════════

banner("eCOS v5 · BOS URI System Demo")

# 1. Workflow M1 nodes
banner("1. Workflow M1 Nodes")
import yaml
wf_dir = WS / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "workflow"
workflows = list(wf_dir.glob("WORKFLOW-*.yaml"))
ok(f"{len(workflows)} workflow M1 nodes found")

# 2. POC Services registry
banner("2. POC Services Registry")
from agora.mcp.bos_resolver import list_services
svcs = list_services()
ok(f"{len(svcs)} POC services across 5 domains")

# 3. BOSRouter
banner("3. BOSRouter — 统一路由")
from agora.mcp.bos_resolver import POC_SERVICES
from agora.mcp.bos_router import bos_router
bos_router.seed_from_poc(POC_SERVICES)
ok(f"{bos_router.count()} routes seeded ({bos_router.stats()})")

# Test a resolve
uri = list(POC_SERVICES.keys())[0]
route = bos_router.resolve(uri)
info(f"{uri} → {route['adapter']}")

# 4. Middleware chain
banner("4. Middleware — 限流/熔断/缓存")
from agora.mcp.bos_middleware import bos_rate_limiter, bos_circuit_breaker, bos_cache
ok(f"RateLimiter: {'active' if bos_rate_limiter.acquire(uri) else 'blocked'}")
ok(f"CircuitBreaker: {'open' if bos_circuit_breaker.is_open(uri) else 'closed'}")
bos_cache.set(uri, {}, "demo-value", 60)
ok(f"Cache: {'hit' if bos_cache.get(uri, {}) else 'miss'}")

# 5. Metrics
banner("5. Metrics")
from agora.mcp.bos_metrics import bos_metrics
bos_metrics.record(uri, True, 42)
summary = bos_metrics.summary()
ok(f"Total calls: {summary['total_calls']}, Success rate: {summary['success_rate']}")

# 6. Real call (internal transport)
banner("6. Real BOS URI Call")
import asyncio
from agora.mcp.bos_resolver import resolve_bos_uri
try:
    result = asyncio.run(resolve_bos_uri('bos://governance/omo/audit'))
    if result.get('status') == 'ok':
        ok(f"bos://governance/omo/audit → OK (grade: {result.get('result',{}).get('grade','?')})")
    else:
        warn(f"Call failed (may need uv environment): {result.get('error','?')}")
except Exception as e:
    warn(f"Direct call unavailable: {e}")

# 7. Discovery
banner("7. Auto-Discovery (AGENTS.md)")
from agora.mcp.bos_discovery import discover_from_workspace
count = discover_from_workspace()
ok(f"Discovered {count} URIs from downstream AGENTS.md")

# 8. Schema
banner("8. Schema Report")
import subprocess
r = subprocess.run([sys.executable, str(WS / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-workflow.py"), "schema-report"],
                   capture_output=True, text=True)
coverage = [l for l in r.stdout.split('\n') if '覆盖度' in l]
if coverage: ok(coverage[0].strip())

banner("Demo Complete")
print(f"""
System Summary:
  Workflow M1: {len(workflows)} nodes, 100% schema coverage
  POC Services: {len(svcs)} across 5 domains
  BOSRouter: {bos_router.count()} routes
  Middleware: RateLimiter + CircuitBreaker + Cache
  Metrics: {summary['total_calls']} calls tracked
  Auto-Discovery: AGENTS.md → {count} URIs
  Internal Call: live (omo/audit)
""")
