#!/usr/bin/env python3
"""Phase 5 E2E Test — L4 Self → L3 Collab → X3 Consensus 全链路验证。

Usage:
    python3 phase5_e2e_test.py
"""

import sys


def test_l4_self():
    """测试 L4 Self Domain: profile + role + vision"""
    from kos.self.api import get_current_role, get_profile, get_vision_summary

    p = get_profile()
    assert p["person"] == "老王", f"Expected 老王, got {p['person']}"
    assert len(p["roles"]) >= 3, f"Expected >=3 roles, got {len(p['roles'])}"
    assert len(p["principles"]) >= 4, f"Expected >=4 principles, got {len(p['principles'])}"

    r = get_current_role()
    assert "role_id" in r, f"Missing role_id in {r}"
    assert "name" in r, f"Missing name in {r}"

    # Context hint
    r_dev = get_current_role(context_hint="系统架构")
    assert r_dev is not None

    vs = get_vision_summary()
    assert len(vs) > 100, f"Vision summary too short: {len(vs)} chars"
    assert "老王" in vs, "Vision should contain person name"

    print("  ✅ test_l4_self PASSED")


def test_l3_collab():
    """测试 L3 Collab Domain: create → claim → complete → get"""
    from kos.collab.api import (
        add_artifact,
        claim_subtask,
        complete_subtask,
        create_task,
        get_task,
    )

    t = create_task(
        title="E2E Test Task",
        goal="验证Phase5全链路",
        creator="user:e2e-test",
        subtasks=[
            {"id": "st1", "title": "Step 1", "status": "pending"},
            {"id": "st2", "title": "Step 2", "status": "pending", "depends_on": [0]},
        ],
    )
    task_id = t["task_id"]
    assert t["status"] == "active", f"Expected active, got {t['status']}"

    # Claim first subtask
    r1 = claim_subtask(task_id, 0, "agent:e2e")
    assert r1.get("status") == "claimed", f"Expected claimed, got {r1}"

    # Claim second (depends on 0, which is in_progress, so should fail)
    r2 = claim_subtask(task_id, 1, "agent:e2e")
    assert r2.get("code") == "DEPENDENCY_NOT_MET", f"Expected DEPENDENCY_NOT_MET, got {r2.get('code')}"

    # Complete first subtask
    r3 = complete_subtask(task_id, 0, "agent:e2e")
    assert r3.get("status") == "completed", f"Expected completed, got {r3}"
    assert r3.get("progress") == 50, f"Expected 50%%, got {r3.get('progress')}"

    # Now claim second
    r4 = claim_subtask(task_id, 1, "agent:e2e")
    assert r4.get("status") == "claimed", f"Expected claimed after dep met, got {r4.get('code')}"

    # Complete second → auto 100%
    r5 = complete_subtask(task_id, 1, "agent:e2e")
    assert r5.get("progress") == 100, f"Expected 100%%, got {r5.get('progress')}"
    assert r5.get("task_status") == "done", f"Expected done, got {r5.get('task_status')}"

    # Add artifact
    t2 = add_artifact(task_id, {"type": "report", "uri": "file:///tmp/e2e-report.md"})
    assert len(t2["artifacts"]) >= 1

    # Get final
    t3 = get_task(task_id)
    assert t3 is not None
    assert t3["status"] == "done"

    print("  ✅ test_l3_collab PASSED")


def test_x3_consensus():
    """测试 X3 Consensus: L1/L2/L3 create → get → renew"""
    from kos.consensus.api import (
        create_consensus,
        get_consensus,
        get_entity_consensus,
        renew_consensus,
    )

    # L1
    c1 = create_consensus("e2e:entity", ["agent:e2e"], "E2E L1共识")
    assert c1["level"] == 1
    assert c1["status"] == "active"

    # L2
    c2 = create_consensus("e2e:entity", ["agent:e2e", "user:老王"], "E2E L2共识")
    assert c2["level"] == 2
    assert c2["status"] == "active"

    # L3
    c3 = create_consensus("e2e:entity", ["redteam:tester"], "E2E L3共识")
    assert c3["level"] == 3

    # Get by entity
    cons = get_entity_consensus("e2e:entity")
    assert len(cons) >= 1, f"Expected >=1 active consensus, got {len(cons)}"

    # Renew L1
    r = renew_consensus(c1["consensus_id"])
    assert r.get("status") == "renewed"
    assert r["consensus"]["level"] == 1

    print("  ✅ test_x3_consensus PASSED")


def test_mcp_tools():
    """验证所有13个MCP工具定义"""
    from kos.self.mcp import SELF_TOOLS
    from kos.collab.mcp import COLLAB_TOOLS
    from kos.consensus.mcp import CONSENSUS_TOOLS

    all_tools = {}
    all_tools.update(SELF_TOOLS)
    all_tools.update(COLLAB_TOOLS)
    all_tools.update(CONSENSUS_TOOLS)

    expected = [
        "self.get_profile", "self.get_current_role", "self.get_vision_summary",
        "collab.create_task", "collab.get_task", "collab.list_tasks",
        "collab.update_task", "collab.claim_subtask", "collab.add_artifact",
        "consensus.create", "consensus.get", "consensus.list_expired", "consensus.renew",
    ]
    for tool_name in expected:
        assert tool_name in all_tools, f"Missing tool: {tool_name}"
        assert "description" in all_tools[tool_name], f"Missing description in {tool_name}"
        assert "inputSchema" in all_tools[tool_name], f"Missing inputSchema in {tool_name}"

    print(f"  ✅ test_mcp_tools PASSED ({len(expected)} tools verified)")


def main():
    print("Phase 5 E2E Test — L4 → L3 → X3 全链路验证")
    print("=" * 50)

    try:
        test_mcp_tools()
        test_l4_self()
        test_l3_collab()
        test_x3_consensus()
    except AssertionError as e:
        print(f"\n❌ FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 50)
    print("Phase5 E2E: ALL PASSED ✅")


if __name__ == "__main__":
    main()
