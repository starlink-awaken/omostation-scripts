"""跨域+LLM 实战 demo — P37-W2.

POC 模式 (默认, 无 API key): 走本地 mock, 调 5 URI 跨域, 跑通派发闭环.
真 API 模式 (有 ANTHROPIC_API_KEY): 调 Claude 3.5 Sonnet 用 tool_use 串联.

用法:
    uv run python scripts/llm_bos_demo.py
    ANTHROPIC_API_KEY=sk-... uv run python scripts/llm_bos_demo.py

POC 设计: 不引入 anthropic 依赖, mock 模式跑通即可.
"""

from __future__ import annotations

import asyncio
import os
import sys

from lib.bootstrap import workspace_root, setup_omo_src

WORKSPACE = workspace_root()
setup_omo_src(WORKSPACE / "projects" / "agora" / "src")

from omo.omo_llm_bos_bridge import (  # noqa: E402
    bos_uri_tool_schema,
    invoke_bos_uri_tool,
    list_bos_uris_tool,
    TOOL_DISPATCHER,
)


# 真实场景问题
REAL_SCENARIO_QUESTION = (
    "请用 BOS URI 工具调研 '2026-06 kairon 提交趋势' 这个主题. "
    "调用顺序: 1) bos://memory/kos/search 搜 'kairon commits' "
    "2) bos://analysis/minerva/research 研究 'kairon 提交趋势' "
    "3) bos://analysis/minerva/draft 生成草稿 "
    "4) bos://analysis/iris/transform 转换格式 "
    "5) bos://capability/forge/list-tools 列出工具 "
    "请逐步调用并给出综合调研报告."
)


def _print_banner(title: str) -> None:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def _safe_status(r: dict) -> str:
    return r.get("status", "?")


def mock_mode_runner() -> dict:
    """POC: 无 API key, 用 mock 模式 — 派发器本地闭环."""
    print("[POC 模式] 无 ANTHROPIC_API_KEY, 走 mock 模式 (派发器本地闭环)")
    print()
    print(f"用户问题: {REAL_SCENARIO_QUESTION}")
    print()

    # 0) 先 list_bos_uris 一下, 模拟 LLM 上下文探索
    listed = list_bos_uris_tool()
    print(f"  [list_bos_uris] 已注册 URI: {listed.get('count', '?')}")
    print()

    # 1) 5 跨域 URI 串联
    pipeline = [
        ("bos://memory/kos/search", {"query": "kairon commits"}),
        ("bos://analysis/minerva/research", {"topic": "kairon 提交趋势"}),
        ("bos://analysis/minerva/draft", {"topic": "kairon 提交趋势"}),
        ("bos://analysis/iris/transform", {}),
        ("bos://capability/forge/list-tools", {}),
    ]
    results = []
    for uri, args in pipeline:
        r = asyncio.run(invoke_bos_uri_tool(uri, args))
        results.append({"uri": uri, "args": args, "result": r})
        print(f"  [invoke] {uri}")
        print(f"    -> status: {_safe_status(r)}")
        if "domain" in r:
            print(f"    -> parsed: domain={r['domain']}, pkg={r['package']}, action={r['action']}")
        if "note" in r:
            print(f"    -> note: {r['note']}")
        if "error" in r:
            print(f"    -> error: {r['error']}")
        print()

    return {
        "mode": "mock",
        "scenario": "2026-06 kairon 提交趋势",
        "calls": results,
        "summary": (
            "[mock 模式] 5 URI 调用均已派发, status 序列 = "
            + ", ".join(_safe_status(r["result"]) for r in results)
        ),
    }


def real_mode_runner() -> dict:
    """真 API 模式: 调 Claude 用 tool_use."""
    try:
        import anthropic  # type: ignore[import-not-found]
    except ImportError:
        print("  [跳过] anthropic 包未装, 走 mock 模式")
        return mock_mode_runner()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  [跳过] ANTHROPIC_API_KEY 未设, 走 mock 模式")
        return mock_mode_runner()

    client = anthropic.Anthropic()
    print("[真 API 模式] Claude + BOS URI tool_use...")
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        tools=bos_uri_tool_schema(),
        messages=[{"role": "user", "content": REAL_SCENARIO_QUESTION}],
    )

    # 处理 tool_use 块
    results = []
    for block in response.content:
        if block.type == "tool_use":
            tool_name = block.name
            tool_args = block.input
            print(f"  [LLM->tool] {tool_name}({tool_args})")
            dispatcher = TOOL_DISPATCHER.get(tool_name)
            if dispatcher is None:
                result = {"error": f"unknown_tool: {tool_name}"}
            else:
                result = dispatcher(tool_args)
            results.append({"tool": tool_name, "args": tool_args, "result": result})
            print(f"    -> {_safe_status(result) if isinstance(result, dict) else '?'}")

    # 让 LLM 综合
    final = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        tools=bos_uri_tool_schema(),
        messages=[
            {"role": "user", "content": REAL_SCENARIO_QUESTION},
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": "请综合以上调用结果, 给出 '2026-06 kairon 提交趋势' 的最终报告."},
        ],
    )

    final_text = ""
    for blk in final.content:
        if getattr(blk, "type", None) == "text":
            final_text += blk.text

    return {
        "mode": "anthropic",
        "scenario": "2026-06 kairon 提交趋势",
        "calls": results,
        "final_report": final_text,
    }


def main() -> int:
    if os.environ.get("ANTHROPIC_API_KEY"):
        result = real_mode_runner()
    else:
        result = mock_mode_runner()

    _print_banner("综合报告")
    if "final_report" in result and result["final_report"]:
        print(result["final_report"])
    else:
        print(result.get("summary", "[no summary]"))
    print()
    print(f"[mode] {result.get('mode')}")
    print(f"[calls] {len(result.get('calls', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
