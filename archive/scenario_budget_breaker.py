#!/usr/bin/env python3
"""
Scenario Experiment 2: Budget Breaker
Verify real-world cost-governance and OMO debt integration.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

# Setup paths
from lib.bootstrap import workspace_root
from lib.yaml_utils import load_yaml
ROOT = workspace_root()
sys.path.insert(0, str(ROOT / "projects" / "runtime" / "src"))
sys.path.insert(0, str(ROOT / "projects" / "llm-gateway" / "src"))

def run_experiment():
    print("🧪 Starting Scenario Experiment 2: Budget Breaker")
    
    # 1. Setup Environment
    os.environ["WORKSPACE"] = str(ROOT)
    os.environ["RUNTIME_HOME"] = str(ROOT / "runtime")
    
    from runtime.executor.engine import AgentRuntime
    from llm_gateway.budget import get_remaining_budget
    
    # Check current budget status
    remaining = get_remaining_budget()
    print(f"📊 Current Global Remaining Budget: ${remaining if remaining is not None else 'UNLIMITED'}")

    # 2. Trigger Budget Violation
    # We use a very low budget (0.000001 USD) for a task that will definitely exceed it
    task_id = f"stress-test-budget-{datetime.now(UTC).strftime('%H%M%S')}"
    print(f"🎯 Triggering task {task_id} with $0.000001 budget...")
    
    runtime = AgentRuntime()
    result = runtime.run_task(
        "Explain the importance of architectural decoupling in eCOS v6 in great detail.",
        context={
            "task_id": task_id,
            "llm_budget_usd": 0.000001,
            "llm_max_output_tokens": 1024
        }
    )

    # 3. Verify Interception
    if result.get("error") and "Budget policy blocked" in result["error"]:
        print(f"✅ SUCCESS: Task was correctly blocked. Error: {result['error']}")
    else:
        print(f"❌ FAILURE: Task was not blocked as expected. Result: {result}")
        return False

    # 4. Verify OMO Debt Registration
    debt_path = ROOT / ".omo" / "debt" / "items" / f"DEBT-OPC-P4-BUDGET-{task_id.upper()}.yaml"
    if debt_path.exists():
        print(f"✅ SUCCESS: OMO Debt record created at {debt_path}")
        print("📄 Debt Content Summary:")
        debt = load_yaml(debt_path)
        print(f"   - ID: {debt['id']}")
        print(f"   - Severity: {debt['severity']}")
        print(f"   - Last Seen: {debt['last_seen_at']}")
    else:
        print(f"❌ FAILURE: OMO Debt record NOT found at {debt_path}")
        # List items for debugging
        print("   Current items in debt directory:")
        for item in (ROOT / ".omo" / "debt" / "items").glob("*.yaml"):
            print(f"   - {item.name}")
        return False

    print("\n🎉 Experiment 2 Passed: Full cost-governance loop verified.")
    return True

if __name__ == "__main__":
    if run_experiment():
        sys.exit(0)
    else:
        sys.exit(1)
