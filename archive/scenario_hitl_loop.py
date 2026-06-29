#!/usr/bin/env python3
"""
Scenario Experiment 4: HITL Approval Loop
Verify the MutationProposal and Cockpit HITL workflow.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from datetime import UTC, datetime

# Setup paths
from lib.bootstrap import workspace_root
ROOT = workspace_root()
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))
sys.path.insert(0, str(ROOT / "projects" / "cockpit" / "web"))

async def run_experiment():
    from omo.omo_cockpit_bridge import list_hitl_proposals
    from omo.omo_ingress import remove_debt_item, upsert_debt_item

    print("🧪 Starting Scenario Experiment 4: HITL Approval Loop")
    
    os.environ["WORKSPACE"] = str(ROOT)
    omo_dir = ROOT / ".omo"
    
    # 1. Create a simulated Budget Debt
    debt_id = "DEBT-BUDGET-TEST-001"
    debt_payload = {
        "id": debt_id,
        "title": "Budget Exhausted (Simulation)",
        "description": "Task 'demo' exceeded $0.05 limit.",
        "status": "open",
        "severity": "medium",
        "registered_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    upsert_debt_item(
        omo_dir,
        debt_data=debt_payload,
        ingress_plane="scripts/scenario_hitl_loop.py",
        source_ref=f"scenario:hitl:{debt_id}",
    )
    print(f"📄 Created simulated debt: {debt_id}")

    # 2. Run Evolution Loop to generate Proposal
    from omo.omo_evolution_loop import EvolutionLoop
    loop = EvolutionLoop()
    print("🔄 Running Evolution Loop...")
    loop.run_once()
    
    proposal_id = f"PROP-{debt_id.replace('DEBT-', '')}"
    proposals = list_hitl_proposals(omo_dir)
    if any(item.get("id") == proposal_id for item in proposals):
        print(f"✅ SUCCESS: MutationProposal {proposal_id} generated.")
    else:
        print(f"❌ FAILURE: MutationProposal not generated: {proposal_id}")
        return False

    # 3. Simulate Cockpit HITL Approval
    # We call the logic inside api_proposals.py directly to avoid starting the full server
    from src.cockpit.web.api_proposals import api_approve_proposal
    print(f"⚖️  Simulating Human Approval for {proposal_id}...")

    # Mocking the Path in api_approve_proposal as it might be hardcoded to HOME
    response = await api_approve_proposal(proposal_id)
    
    # Handle both dict and JSONResponse (FastAPI wrap)
    if isinstance(response, dict):
        res = response
    else:
        import json
        res = json.loads(response.body)
    
    if res.get("status") == "ok":
        print(f"✅ SUCCESS: Proposal approved. {res.get('message')}")
    else:
        print(f"❌ FAILURE: Approval logic failed. {res}")
        return False

    # 4. Verify Queue Clearance
    proposals = list_hitl_proposals(omo_dir)
    if not any(item.get("id") == proposal_id for item in proposals):
        print("✅ SUCCESS: Proposal cleared from the queue after approval.")
    else:
        print("❌ FAILURE: Proposal still exists in the queue.")
        return False

    # Cleanup
    remove_debt_item(
        omo_dir,
        debt_id=debt_id,
        actor="scripts/scenario_hitl_loop.py",
        source_ref=f"scenario:hitl:{debt_id}",
    )
    print("\n🎊 Experiment 4 Passed: HITL Approval Loop verified.")
    return True

if __name__ == "__main__":
    try:
        if asyncio.run(run_experiment()):
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        pass
