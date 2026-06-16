#!/usr/bin/env python3
"""
Scenario Experiment 4: The Evolution Loop
Verify that OMO can actively remediate technical debt.
"""

from __future__ import annotations

import os
import sys
import yaml
from pathlib import Path
from datetime import UTC, datetime

# Setup paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

def run_experiment():
    import logging
    logging.basicConfig(level=logging.INFO)
    print("🧪 Starting Scenario Experiment 4: The Evolution Loop")
    
    os.environ["WORKSPACE"] = str(ROOT)
    print(f"🏠 Workspace Root: {ROOT}")
    debt_dir = ROOT / ".omo" / "debt" / "items"
    debt_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Create a fake Budget Exhausted debt
    debt_id = f"DEBT-EVOLUTION-TEST-{datetime.now(UTC).strftime('%H%M%S')}"
    debt_path = debt_dir / f"{debt_id}.yaml"
    
    debt_payload = {
        "id": debt_id,
        "title": "Simulation: Budget Exhausted during research",
        "description": "Task 'alpha-research' hit $0.05 budget limit using gpt-4.",
        "status": "open",
        "severity": "medium",
        "registered_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    
    debt_path.write_text(yaml.safe_dump(debt_payload))
    print(f"📄 Created test debt: {debt_id}")

    # 2. Run Evolution Loop (Single Pass)
    from omo.omo_evolution_loop import EvolutionLoop
    loop = EvolutionLoop()
    
    print("🔄 Running Evolution Loop...")
    triggered = loop.run_once()

    # 3. Verify
    if triggered > 0:
        print(f"✅ SUCCESS: Evolution Loop detected and triggered {triggered} remediation(s).")
        # Cleanup
        debt_path.unlink()
        return True
    else:
        print("❌ FAILURE: Evolution Loop failed to detect the test debt.")
        return False

if __name__ == "__main__":
    if run_experiment():
        sys.exit(0)
    else:
        sys.exit(1)
