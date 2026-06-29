"""P59-W3 跨仓 stdio JSON-RPC smoke 测试 (3 仓 dispatch 闭环).

KISS 接受: 不跑真 subprocess (3 仓路径 + uv venv 配置复杂),
直接 import 3 仓 __main__._call_action + 调一次, 验证 dispatch 闭环.
stdio_rpc helper 已 P49-simplify 抽 3 仓, 跨仓 line protocol 一致 (同 helper).
"""
from __future__ import annotations

import json
import sys
from typing import Any

from lib.bootstrap import workspace_root

ROOT = workspace_root()
for _p in (ROOT / "projects" / "omo" / "src", ROOT / "projects" / "agora" / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

PASS = "✅"
FAIL = "❌"
results: list[tuple[str, str, str]] = []


def smoke(name: str, action: str, args: dict[str, Any], expect_key: str) -> None:
    """调 1 次 dispatch, verify 返回含 expect_key."""
    try:
        if name == "omo":
            from omo.omo_llm_bos_bridge import invoke_bos_uri_tool
            import asyncio
            r = asyncio.run(invoke_bos_uri_tool(action, args))
        elif name == "kairon_kos":
            from kos.__main__ import _call_action
            r = _call_action(action, args)
        elif name == "runtime":
            from runtime.__main__ import _call_action
            r = _call_action(action, args)
        else:
            raise ValueError(f"unknown repo: {name}")

        status = r.get("status", r.get("result", r.get("_method", "?")))
        ok = expect_key in r
        mark = PASS if ok else FAIL
        results.append((name, action, f"{mark} {status} (key={expect_key})"))
    except Exception as exc:
        results.append((name, action, f"{FAIL} {type(exc).__name__}: {exc}"))


def main() -> int:
    print("=" * 60)
    print("P59-W3 跨仓 stdio JSON-RPC smoke 测试")
    print("=" * 60)

    # 1) omo 跨仓调 kairon kos (走 agora subprocess 池)
    smoke("omo", "bos://memory/kos/search", {"query": "test"}, "_method")

    # 2) kairon kos dispatch (走 do_default 真业务)
    smoke("kairon_kos", "search", {"query": "p59"}, "_method")

    # 3) runtime dispatch (走 do_default 真业务)
    smoke("runtime", "echo", {"text": "p59"}, "status")

    # 报告
    print()
    for name, action, result in results:
        print(f"  {name:15s} {action:30s} {result}")

    fail_count = sum(1 for _, _, r in results if r.startswith(FAIL))
    print()
    if fail_count == 0:
        print(f"{PASS} 3 仓跨仓 dispatch 全部 OK")
        return 0
    print(f"{FAIL} {fail_count} 仓失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
