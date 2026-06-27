#!/usr/bin/env python3
"""
Scenario Experiment 4: The Evolution Loop
Verify that OMO can actively remediate technical debt.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import UTC, datetime

# Setup paths
from lib.bootstrap import workspace_root
ROOT = workspace_root()
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

def run_experiment():
    import logging
    from omo.omo_ingress import remove_debt_item, upsert_debt_item
    
    logging.basicConfig(level=logging.INFO)
    print("🧪 Starting Scenario Experiment 4: The Evolution Loop")
    
    os.environ["WORKSPACE"] = str(ROOT)
    print(f"🏠 Workspace Root: {ROOT}")
    omo_dir = ROOT / ".omo"
    
    # 1. Create a fake Budget Exhausted debt
    debt_id = f"DEBT-EVOLUTION-TEST-{datetime.now(UTC).strftime('%H%M%S')}"
    
    debt_payload = {
        "id": debt_id,
        "title": "Simulation: Budget Exhausted during research",
        "description": "Task 'alpha-research' hit $0.05 budget limit using gpt-4.",
        "status": "open",
        "severity": "medium",
        "registered_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    
    upsert_debt_item(
        omo_dir,
        debt_data=debt_payload,
        ingress_plane="scripts/scenario_evolution_loop.py",
        source_ref=f"scenario:evolution:{debt_id}",
    )
    print(f"📄 Created test debt: {debt_id}")

    # 2. Run Evolution Loop (Single Pass)
    from omo.omo_evolution_loop import EvolutionLoop
    loop = EvolutionLoop()
    
    print("🔄 Running Evolution Loop...")
    triggered = loop.run_once()

    # 3. Verify
    if triggered > 0:
        print(f"✅ SUCCESS: Evolution Loop detected and triggered {triggered} remediation(s).")
        remove_debt_item(
            omo_dir,
            debt_id=debt_id,
            actor="scripts/scenario_evolution_loop.py",
            source_ref=f"scenario:evolution:{debt_id}",
        )
        return True
    else:
        print("❌ FAILURE: Evolution Loop failed to detect the test debt.")
        return False

if __name__ == "__main__":
    if run_experiment():
        sys.exit(0)
    else:
        sys.exit(1)
