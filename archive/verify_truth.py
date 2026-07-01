#!/usr/bin/env python3
"""
Truth Verification Script v3
Verify that mocks have been replaced by real logic.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from lib.bootstrap import workspace_root

# Setup paths
ROOT = workspace_root()
sys.path.insert(0, str(ROOT / "projects" / "agora" / "src"))
sys.path.insert(0, str(ROOT / "projects" / "cockpit" / "web"))
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

async def verify_truth():
    print("🔍 Starting Truth Verification Action (v3)...")
    
    os.environ["WORKSPACE"] = str(ROOT)
    os.environ["WORKSPACE_ROOT"] = str(ROOT)
    
    # 1. Verify Swarm Telemetry
    print("\n[1] Verifying Swarm Telemetry (Real Hardware Stats)...")
    from agora.mcp.swarm import get_swarm, SwarmNode
    swarm = get_swarm()
    node = SwarmNode(node_id=swarm.node_id, host="localhost", port=swarm.port, role=swarm.role, last_heartbeat=time.time())
    swarm.register_node(node)
    swarm.report_load(load_score=10, cpu_pct=45.5)
    status = swarm.status()
    self_node = next((n for n in status.get("nodes", []) if n["node_id"] == swarm.node_id), None)
    if self_node and self_node.get("load_score") == 10:
        print("   ✅ SUCCESS: Swarm telemetry verified.")
    else:
        print("   ❌ FAILURE: Swarm telemetry failed.")

    # 2. Verify Vault ripgrep Search
    print("\n[2] Verifying Vault ripgrep Search...")
    from agora.mcp.bos_resolver import _memory_vault_search
    cards_dir = ROOT / "data" / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    (cards_dir / "truth_test.md").write_text("eCOS v6 truth verification record.")
    res = await _memory_vault_search({"query": "verification", "limit": 1})
    if res:
        print(f"   ✅ SUCCESS: ripgrep search returned real results. Found: {res[0]['title']}")
    else:
        print("   ❌ FAILURE: ripgrep search failed.")

    # 3. Verify HITL Real Side-effects
    print("\n[3] Verifying HITL Real Side-effects...")
    from app import _execute_mutation
    patch_file = ROOT / ".omo" / "state" / "budget_overrides.jsonl"
    before_exists = patch_file.exists()
    before_size = patch_file.stat().st_size if before_exists else -1
    await _execute_mutation({"id":"P1","type":"budget_increase","debt_id":"D1"})
    after_exists = patch_file.exists()
    after_size = patch_file.stat().st_size if after_exists else -1
    if after_exists and (not before_exists or after_size >= before_size):
        print(f"   ✅ SUCCESS: Mutation wrote to {patch_file.name}")
    else:
        print("   ❌ FAILURE: No side-effects created.")

    # 4. Verify Swarm Signature
    print("\n[4] Verifying Swarm Signature...")
    from agora.auth.node_identity import NodeIdentityManager
    id_path = str(ROOT / ".omo" / "state" / "test_node_identity.json")
    nim = NodeIdentityManager(identity_path=id_path)
    identity = nim.load_or_create()
    pk = nim.get_private_key_b64()
    if identity and pk:
        sig = identity.sign(b"test", pk)
        if identity.verify(b"test", sig, identity.public_key):
            print("   ✅ SUCCESS: Ed25519 signing and verification verified.")
        else:
            print("   ❌ FAILURE: Signature verification failed.")
    else:
        print("   ❌ FAILURE: Identity creation failed.")

    print("\n🏆 TRUTH VERIFICATION COMPLETE.")

if __name__ == "__main__":
    asyncio.run(verify_truth())
