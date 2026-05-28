"""Phase 8 E2E Test — 多Agent协作验证 (T119)

Usage: python3 /Users/xiamingxing/Workspace/phase8_e2e_test.py
"""

import sys


def test_orchestrator():
    """T111-T113: TaskOrchestrator全流程"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("orch", "/Users/xiamingxing/.hermes/plugins/task_orchestrator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    orch = mod.TaskOrchestrator()

    result = orch.create_and_manage("开发Mac mini监控面板，调研现有方案，设计UI原型，编码实现后端+前端")
    assert result["task_id"]
    task_id = result["task_id"]
    print(f"  Task created: {task_id}")

    report = orch.progress_report(task_id)
    assert "进度" in report
    print(f"  Progress report OK")

    trigger = orch.on_subtask_completed(task_id, "step-1")
    print(f"  Trigger: {trigger}")

    final = orch.auto_mark_completed(task_id)
    print(f"  Final: {final.get('status')}")
    print("  ✅ test_orchestrator PASSED")


def test_memory_mcp():
    """T114: Memory MCP Service"""
    import importlib.util, sys as _sys
    spec = importlib.util.spec_from_file_location("mem_mcp", "/Users/xiamingxing/.hermes/memory/mcp_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.handle_memory_set("老王偏好架构先行理论驱动", tags=["principle", "老王"])
    r = mod.handle_memory_get("架构先行")
    assert r["count"] >= 1

    tags_r = mod.handle_memory_list_tags()
    assert "principle" in tags_r["tags"]
    print("  ✅ test_memory_mcp PASSED")


def test_skill_mcp():
    """T115: Skill MCP Service"""
    import importlib.util, sys as _sys
    spec = importlib.util.spec_from_file_location("skl_mcp", "/Users/xiamingxing/.hermes/skills/mcp_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    s = mod.handle_skill_list()
    assert s["count"] >= 5

    r = mod.handle_skill_match("需要设计UI界面")
    assert len(r["results"]) >= 1
    print("  ✅ test_skill_mcp PASSED")


def test_agora_fallback():
    """T120: Agora Fallback"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("afb", "/Users/xiamingxing/.hermes/adapters/agora_fallback.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    fb = mod.get_fallback()
    fb.register_peer("agent:test", "localhost", 9999)
    assert "agent:test" in fb.direct_peers

    r = fb._a2a_call("agent:nonexist", "test.tool", {})
    assert "error" in r
    print("  ✅ test_agora_fallback PASSED")


def test_tool_counts():
    import importlib.util
    spec1 = importlib.util.spec_from_file_location("mem_mcp_test", "/Users/xiamingxing/.hermes/memory/mcp_server.py")
    mem_mod = importlib.util.module_from_spec(spec1)
    spec1.loader.exec_module(mem_mod)
    spec2 = importlib.util.spec_from_file_location("skl_mcp_test", "/Users/xiamingxing/.hermes/skills/mcp_server.py")
    skl_mod = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(skl_mod)

    all_tools = list(mem_mod.TOOLS.keys()) + list(skl_mod.TOOLS.keys())
    assert "memory.get" in all_tools
    assert "skill.list" in all_tools
    print(f"  Memory: {list(mem_mod.TOOLS.keys())}, Skill: {list(skl_mod.TOOLS.keys())}")
    print(f"  Total new MCP tools: {len(all_tools)}")
    print("  ✅ test_tool_counts PASSED")


def main():
    print("Phase 8 E2E — 多Agent协作")
    print("=" * 50)
    tests = [test_tool_counts, test_memory_mcp, test_skill_mcp, test_agora_fallback, test_orchestrator]
    for t in tests:
        t()
    print("\n" + "=" * 50)
    print("Phase8 E2E: ALL PASSED ✅")


if __name__ == "__main__":
    main()
