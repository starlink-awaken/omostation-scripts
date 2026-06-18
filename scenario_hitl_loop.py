#!/usr/bin/env python3
"""
Scenario Experiment 4: HITL Approval Loop
Verify the MutationProposal and Cockpit HITL workflow.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import yaml
from pathlib import Path
from datetime import UTC, datetime

# Setup paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))
sys.path.insert(0, str(ROOT / "projects" / "cockpit" / "web"))

async def run_experiment():
    print("🧪 Starting Scenario Experiment 4: HITL Approval Loop")
    
    os.environ["WORKSPACE"] = str(ROOT)
    debt_dir = ROOT / ".omo" / "debt" / "items"
    proposal_dir = ROOT / ".omo" / "state" / "proposals"
    debt_dir.mkdir(parents=True, exist_ok=True)
    proposal_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Create a simulated Budget Debt
    debt_id = "DEBT-HITL-TEST-001"
    debt_path = debt_dir / f"{debt_id}.yaml"
    debt_payload = {
        "id": debt_id,
        "title": "Budget Exhausted (Simulation)",
        "description": "Task 'demo' exceeded $0.05 limit.",
        "status": "open",
        "severity": "medium",
        "registered_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    debt_path.write_text(yaml.safe_dump(debt_payload))
    print(f"📄 Created simulated debt: {debt_id}")

    # 2. Run Evolution Loop to generate Proposal
    from omo.omo_evolution_loop import EvolutionLoop
    loop = EvolutionLoop()
    print("🔄 Running Evolution Loop...")
    loop.run_once()
    
    proposal_id = f"PROP-{debt_id.replace('DEBT-', '')}"
    proposal_path = proposal_dir / f"{proposal_id}.yaml"
    
    if proposal_path.exists():
        print(f"✅ SUCCESS: MutationProposal {proposal_id} generated.")
    else:
        print(f"❌ FAILURE: MutationProposal not generated at {proposal_path}")
        return False

    # 3. Simulate Cockpit HITL Approval
    # We call the logic inside dashboard_server.py directly to avoid starting the full server
    from src.cockpit.dashboard_server import api_approve_proposal
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
    if not proposal_path.exists():
        print("✅ SUCCESS: Proposal cleared from the queue after approval.")
    else:
        print("❌ FAILURE: Proposal still exists in the queue.")
        return False

    # Cleanup
    debt_path.unlink()
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
