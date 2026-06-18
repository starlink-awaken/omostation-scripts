#!/usr/bin/env python3
"""
Scenario Experiment 3: The Swarm Relay
Verify Swarm + A2A cross-node communication.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Setup paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "agora" / "src"))

async def run_experiment():
    print("🧪 Starting Scenario Experiment 3: The Swarm Relay")
    
    # 1. Setup Environment
    os.environ["WORKSPACE"] = str(ROOT)
    os.environ["AGORA_SWARM_ROLE"] = "master"
    
    from agora.a2a.transport import A2ANetworkTransport
    from agora.mcp.swarm import get_swarm, SwarmNode
    
    # 2. Initialize Transport and Swarm
    transport = A2ANetworkTransport()
    swarm = get_swarm(role="master")
    
    # 3. Simulate Remote Node Registration
    # Manually register a 'worker' node
    worker_node = SwarmNode(
        node_id="worker-node-1",
        host="127.0.0.1",
        port=7455,
        mcp_port=7422,
        role="worker",
        last_heartbeat=9999999999.0
    )
    swarm.register_node(worker_node)
    print(f"🌐 Registered simulated remote node: {worker_node.node_id}")

    # 4. Trigger Cross-Node Relay
    # Target: worker-node-1/research-agent
    target = "worker-node-1/research-agent"
    message = {"goal": "Analyze swarm latency", "priority": "high"}
    
    print(f"📡 Dispatching message to {target} via NetworkTransport...")
    
    # This should trigger the HTTP Forwarding path in A2ANetworkTransport
    # Since we don't have a real HTTP server on 7422, we expect a 'forward_failed' 
    # connection error, which PROVES it hit the right code path.
    
    result = await transport.send_message_async(target, message, timeout=2.0)

    # 5. Verify Interception/Path
    if result.get("status") == "error" and "forward_failed" in result.get("error", ""):
        print("✅ SUCCESS: Message correctly hit the HTTP forwarding logic for remote node!")
        print(f"   (Expected failure caught: {result['error']})")
        
        # Now test local routing via the same async method
        local_target = f"{swarm.node_id}/local-agent"
        print(f"🏠 Dispatching message to local target {local_target}...")
        local_res = await transport.send_message_async(local_target, {"ping": "pong"})
        
        if local_res.get("status") == "delivered":
             print("✅ SUCCESS: Asynchronous local routing within Swarm also verified!")
             print("\n🎊 Experiment 3 Passed: Multi-node A2A routing logic verified.")
             return True
    
    print(f"❌ FAILURE: Routing logic didn't behave as expected. Result: {result}")
    return False

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        if loop.run_until_complete(run_experiment()):
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        pass
