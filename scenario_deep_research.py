#!/usr/bin/env python3
"""
Deep Scenario: Swarm-Native Deep Research Pipeline
-------------------------------------------------
This script demonstrates the full synergy of the eCOS v6 Spines:
1. Compute Spine: Budget pre-check and cost governance.
2. Memory Spine: Concurrent aggregated search (KOS + gbrain + Vault).
3. Swarm Spine: Distributed task routing (simulated multi-node).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import UTC, datetime

# Setup paths to include all core modules
from lib.bootstrap import workspace_root

# Setup paths to include all core modules
ROOT = workspace_root()
sys.path.insert(0, str(ROOT / "projects" / "agora" / "src"))
sys.path.insert(0, str(ROOT / "projects" / "runtime" / "src"))
sys.path.insert(0, str(ROOT / "projects" / "aetherforge" / "packages" / "gateway" / "src"))
sys.path.insert(0, str(ROOT / "projects" / "aetherforge" / "packages" / "mesh" / "src"))
sys.path.insert(0, str(ROOT / "projects" / "aetherforge" / "packages" / "swarm" / "src"))

async def run_deep_research(topic: str):
    print(f"🚀 Launching Deep Research Pipeline for: '{topic}'")
    print("=" * 60)
    
    os.environ["WORKSPACE"] = str(ROOT)
    os.environ["RUNTIME_HOME"] = str(ROOT / "runtime")

    from agora.server.mcp import _init_proxy
    from agora.mcp.bos_router import bos_router
    from agora.mcp.bos_resolver import resolve_bos_uri, _memory_all_search
    from agora.mcp_proxy.manager import ProxyManager
    from llm_gateway.budget import check_budget_limit, get_remaining_budget
    from runtime.executor.engine import AgentRuntime

    # --- Step 1: Infrastructure & Compute Spine (Budget) ---
    print("\n[Step 1] Compute Spine: Validating Quota & Budget...")
    await _init_proxy() # Loads POC_SERVICES and registers routes
    
    remaining = get_remaining_budget()
    print(f"   - Global Remaining: ${remaining if remaining is not None else 'UNLIMITED'}")
    
    # We set a local budget of $0.05 for this research session
    local_budget = 0.05
    try:
        # Pre-check for the Planner Agent (estimated 2000 tokens)
        check_budget_limit(
            model_id="deepseek/deepseek-chat",
            input_tokens=2000,
            local_budget_limit=local_budget,
            task_id="deep-research-planner"
        )
        print(f"   - Budget check PASSED (Local Limit: ${local_budget})")
    except Exception as e:
        print(f"   - ❌ Budget check FAILED: {e}")
        return

    # --- Step 2: Memory Spine (Context Gathering) ---
    print("\n[Step 2] Memory Spine: Aggregated Knowledge Retrieval...")
    print(f"   - Querying bos://memory/local/all-search for '{topic}' context...")
    
    mem_res = await _memory_all_search({"query": topic, "limit": 10})
    print(f"   - Found {mem_res.get('total_hits')} hits from {len(mem_res.get('sources_searched', []))} sources.")
    
    context_snippet = ""
    for hit in mem_res.get("results", []):
        source = hit.get("_source", "unknown")
        title = hit.get("title", hit.get("fact", "No title"))
        context_snippet += f"Source [{source}]: {title}\n"
    
    print("   - Context gathered successfully.")

    # --- Step 3: Swarm Spine (Distributed Execution) ---
    print("\n[Step 3] Swarm Spine: Task Decomposition & Delegation...")
    
    # Simulate a Swarm by creating a ProxyManager with two 'remote' nodes
    pm = ProxyManager()
    
    # In a real swarm, these would be discovered. Here we manually register them.
    # Node 1: Specializes in Architectural Analysis
    await pm.add_service({
        "name": "worker-node-1-arch",
        "mcp_endpoint": "stdio",
        "command": "bun",
        "args": ["run", "--cwd", "projects/gbrain", "src/cli.ts", "serve"],
    })
    # Node 2: Specializes in Scalability Analysis
    await pm.add_service({
        "name": "worker-node-2-perf",
        "mcp_endpoint": "stdio",
        "command": "uv",
        "args": ["run", "--package", "kos", "python", "-m", "kos.cli", "serve", "--mcp"],
    })

    # Register these specific sub-tasks to the 'remote' nodes in the Router
    bos_router.register("bos://research/worker-1/arch", adapter="proxy", config={"service_name": "worker-node-1-arch", "node_id": "remote-node-1"})
    bos_router.register("bos://research/worker-2/scalability", adapter="proxy", config={"service_name": "worker-node-2-perf", "node_id": "remote-node-2"})

    print("   - Dispatching parallel sub-tasks to Swarm nodes...")
    
    # Define sub-tasks
    sub_tasks = [
        ("bos://research/worker-1/arch", "Analyze the benefits of architectural decoupling in eCOS v6."),
        ("bos://research/worker-2/scalability", "Evaluate the scalability of the Swarm A2A network transport.")
    ]

    async def _delegate(uri, prompt):
        print(f"     📡 Sending sub-task to {uri}...")
        # In this demo, we use resolve_bos_uri which is now swarm-aware
        # and will route 'proxy' adapter calls through the provided ProxyManager.
        # Since our simulated workers are just standard MCP servers, we call their 'execute' tool if available,
        # or just simulate the execution if we don't have a generic 'think' tool on them.
        # For the sake of the demo, we'll call gbrain's search on worker 1 and KOS on worker 2.
        
        target_action = "search" if "worker-1" in uri else "semantic_search"
        return await resolve_bos_uri(uri + "/" + target_action, {"query": prompt}, proxy_manager=pm)

    # Execute in parallel
    swarm_results = await asyncio.gather(*[_delegate(u, p) for u, p in sub_tasks])
    print(f"   - Received results from {len(swarm_results)} swarm nodes.")

    # --- Step 4: Final Synthesis (Planner) ---
    print("\n[Step 4] Synthesis: Generating Final Deep Research Report...")
    
    runtime = AgentRuntime()
    final_query = f"""
Compose a comprehensive research report on the topic: '{topic}'.
Base your analysis on the following gathered context and swarm-delegated results:

MEM_CONTEXT:
{context_snippet}

SWARM_RESULTS:
{json.dumps(swarm_results, indent=2, ensure_ascii=False)[:2000]}
"""
    
    # Execute the final synthesis
    report = runtime.run_task(
        final_query,
        context={
            "task_id": "deep-research-final-synthesis",
            "llm_budget_usd": 0.02 # Reserved budget for synthesis
        }
    )

    print("\n" + "=" * 60)
    print("💎 FINAL RESEARCH REPORT 💎")
    print("-" * 60)
    if report.get("content"):
        print(report["content"])
    else:
        print(f"❌ Error during synthesis: {report.get('error')}")
    print("-" * 60)
    
    # Show debt loop if any (for example if synthesis almost hit the budget)
    print("\n[Audit] Checking OMO Debt Loop status...")
    for item in (ROOT / ".omo" / "debt" / "items").glob("DEBT-OPC-P4-BUDGET-*.yaml"):
        if datetime.fromtimestamp(item.stat().st_mtime, UTC).date() == datetime.now(UTC).date():
            print(f"   ⚠️ Active Budget Debt detected: {item.name}")

    print("\n🎉 Deep Research Scenario Completed Successfully.")

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    try:
        topic = sys.argv[1] if len(sys.argv) > 1 else "eCOS v6 Architecture and Scalability"
        asyncio.run(run_deep_research(topic))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"🔥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
