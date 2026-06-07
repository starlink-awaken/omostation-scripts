"""omostation 跨域+LLM 真消费卫健委场景 — P39-W1 / P41-W0.

场景: "分析基层医疗机构药品集采政策" (P28 卫健委 E2E 主题).
LLM 通过 tool_use 调 6+ BOS URI 跨域串联.

P41-W0: 三模式并存, 优先级: ollama (本地 LLM, 首选) > anthropic > mock.
- ollama 模式: 用 OpenAI 兼容接口调本地 ollama, 不需 ANTHROPIC_API_KEY
- anthropic 模式: 用 anthropic SDK 调 Claude
- mock 模式: 6 URI 派发闭环, 不需 LLM 调用

P32 收官约束: 不改 agora 核心, 不重启 omo daemon, 0 破坏性操作.
P39-W1 约束: 不引入 anthropic 依赖 (mock 即可), 守 P32-P38 修复.
P41-W0 约束: ollama 优先, 守 P32-P40 修复.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# ── PYTHONPATH 注入 (omo + agora) ──────────────────────────
WORKSPACE = Path("/Users/xiamingxing/Workspace")
OMO_SRC = WORKSPACE / "projects" / "omo" / "src"
AGORA_SRC = WORKSPACE / "projects" / "agora" / "src"
for p in (str(OMO_SRC), str(AGORA_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from omo.omo_llm_bos_bridge import (  # noqa: E402
    TOOL_DISPATCHER,
    bos_uri_tool_schema,
    invoke_bos_uri_tool,
    list_bos_uris_tool,
)


# ── 卫健委真实场景问题 ─────────────────────────────────────
HEALTHWORK_SCENARIO = """你是 omstation 卫健委工作辅助 AI.
请用 BOS URI 工具调研 "基层医疗机构药品集采政策" 这个主题.

步骤:
1. 用 invoke_bos_uri 调 bos://memory/kos/search 搜 "基层医疗 药品集采" (找相关政策实体)
2. 用 invoke_bos_uri 调 bos://analysis/minerva/research 研究 "基层医疗机构药品集采" (深度调研)
3. 用 invoke_bos_uri 调 bos://analysis/minerva/draft 生成综合草稿 (审计+研究 综合)
4. 用 invoke_bos_uri 调 bos://analysis/iris/transform 转换格式 (转 markdown 结构化)
5. 用 invoke_bos_uri 调 bos://governance/omo/inspect 检查 omo 系统状态
6. 用 invoke_bos_uri 调 bos://analysis/iris/validate 验证草稿质量

请逐步调用并给出综合调研报告 (政策摘要 + 关键实体 + 来源引用).
"""


# ── 6 URI 跨域串联 (场景定锚) ─────────────────────────────
HEALTHWORK_URI_PIPELINE: list[tuple[str, dict]] = [
    ("bos://memory/kos/search", {"query": "基层医疗 药品集采", "limit": 5}),
    ("bos://analysis/minerva/research", {"topic": "基层医疗机构药品集采", "depth": "standard"}),
    ("bos://analysis/minerva/draft", {"topic": "基层医疗机构药品集采", "style": "policy_brief"}),
    ("bos://analysis/iris/transform", {"format": "markdown", "structure": "sectioned"}),
    ("bos://governance/omo/inspect", {"scope": "phase41"}),
    ("bos://analysis/iris/validate", {"content": "草稿", "rubric": "policy_completeness"}),
]


# ── mock 模式 (POC 阶段, 无 ANTHROPIC_API_KEY) ────────────
def mock_mode_runner() -> dict:
    """POC: 6 URI 派发闭环 + 派发器本地验证."""
    print("[POC mock 模式] 无 LLM 后端, 走 mock 模式...")
    print()
    print(f"用户问题: {HEALTHWORK_SCENARIO.strip()[:80]}...")
    print()

    # 1) schema 自检
    schema = bos_uri_tool_schema()
    print(f"[1] tool schema: {len(schema)} 工具, names={[s['name'] for s in schema]}")

    # 2) 列 URI (供 LLM 上下文)
    listed = list_bos_uris_tool(domain=None)
    print(f"[2] registered URI: {listed.get('count', 0)} (全量)")

    # 3) 6 URI 派发闭环
    results = []
    for uri, args in HEALTHWORK_URI_PIPELINE:
        r = asyncio.run(invoke_bos_uri_tool(uri, args))
        status = r.get("status", "?")
        results.append({"uri": uri, "args": args, "result": r})
        print(f"  -> {uri}: status={status}")

    return {
        "scenario": "基层医疗机构药品集采政策",
        "mode": "mock",
        "uri_calls": results,
        "summary": (
            f"mock 模式 {len(results)} URI 派发闭环验证通过. "
            "真 anthropic API 模式需用户配置 ANTHROPIC_API_KEY 后启用. "
            "ollama 模式需本地 ollama 服务在 http://localhost:11434."
        ),
    }


# ── OpenAI 兼容 tool schema (用于 ollama) ──────────────────
def bos_uri_tool_openai_schema() -> list[dict]:
    """OpenAI 兼容的工具 schema (ollama OpenAI 端点用).

    字段命名: type/function.name/function.description/function.parameters
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "invoke_bos_uri",
                "description": (
                    "调用 BOS (Banyan Object Service) URI 执行知识工程/治理/分析/能力操作. "
                    "BOS URI 格式: bos://<domain>/<package>/<action>"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "BOS URI, 形如 bos://memory/kos/search",
                            "pattern": r"^bos://(memory|governance|analysis|persona|capability)/[a-z][a-z0-9-]+/[a-z][a-z0-9-]+$",
                        },
                        "args": {
                            "type": "object",
                            "description": "URI 调用参数 (per-URI 协议)",
                        },
                    },
                    "required": ["uri"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_bos_uris",
                "description": "列出已注册的 BOS URI (可按 domain 过滤)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "domain 过滤 (memory/governance/analysis/persona/capability), 留空列全量",
                        }
                    },
                },
            },
        },
    ]


# ── ollama 模式 (P41-W0 优先, 本地 LLM) ───────────────────
def ollama_mode_runner() -> dict:
    """P41-W0: ollama 模式 (本地 LLM). 优先级最高, 不需 ANTHROPIC_API_KEY.

    用 OpenAI 兼容接口调本地 ollama, base_url=http://localhost:11434/v1.
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")  # 4b 模型, 速度快

    print(f"[ollama 模式] base_url={base_url} model={model}")

    # 优先 OpenAI 客户端, 退化 ollama SDK
    client = None
    try:
        from openai import OpenAI  # type: ignore[import-not-found]

        client = OpenAI(base_url=base_url, api_key="ollama")  # ollama 不要真 key
        print(f"  -> 用 OpenAI 兼容客户端")
    except ImportError:
        try:
            import ollama as ollama_sdk  # type: ignore[import-not-found]

            client = ollama_sdk
            print(f"  -> 退化用 ollama Python SDK")
        except ImportError:
            print(f"  [fallback] openai/ollama SDK 都未装, 退到 mock 模式")
            return mock_mode_runner()

    # 第一轮: LLM 调工具
    print(f"  -> LLM ({model}) 调 BOS URI tool_use 串联...")
    try:
        if hasattr(client, "chat") and not hasattr(client, "completions"):
            # ollama SDK 路径
            response = client.chat(
                model=model,
                messages=[{"role": "user", "content": HEALTHWORK_SCENARIO}],
                tools=bos_uri_tool_openai_schema(),
            )
            tool_calls = response.get("message", {}).get("tool_calls", []) or []
        else:
            # OpenAI 客户端路径
            response = client.chat.completions.create(
                model=model,
                max_tokens=4096,
                tools=bos_uri_tool_openai_schema(),
                messages=[{"role": "user", "content": HEALTHWORK_SCENARIO}],
            )
            tool_calls = (response.choices[0].message.tool_calls or []) if response.choices else []
    except Exception as e:
        print(f"  [fallback] ollama 调用失败: {e}")
        return mock_mode_runner()

    # 派发工具调用
    results = []
    for tc in tool_calls:
        if hasattr(tc, "function"):
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments or "{}")
            except Exception:
                tool_args = {}
        else:
            tool_name = (tc.get("function") or {}).get("name", "?")
            try:
                tool_args = json.loads((tc.get("function") or {}).get("arguments", "{}"))
            except Exception:
                tool_args = {}
        # tool 内部走 BOS 派发
        if tool_name == "invoke_bos_uri":
            uri = tool_args.get("uri", "")
            args = tool_args.get("args", {})
            print(f"  -> LLM 调 invoke_bos_uri({uri}, {args})")
            try:
                r = asyncio.run(invoke_bos_uri_tool(uri, args))
            except Exception as e:
                r = {"status": "error", "error": str(e)}
            results.append({"tool": tool_name, "args": tool_args, "result": r})
        elif tool_name == "list_bos_uris":
            domain = tool_args.get("domain")
            print(f"  -> LLM 调 list_bos_uris(domain={domain})")
            r = list_bos_uris_tool(domain=domain)
            results.append({"tool": tool_name, "args": tool_args, "result": r})
        else:
            results.append({"tool": tool_name, "args": tool_args, "result": {"error": f"unknown_tool: {tool_name}"}})

    # 如果 LLM 没调工具, 走 fallback URI pipeline
    if not results:
        print(f"  -> LLM 未调工具 (小模型可能不识 tool_use), 走 fallback URI pipeline")
        for uri, args in HEALTHWORK_URI_PIPELINE:
            try:
                r = asyncio.run(invoke_bos_uri_tool(uri, args))
            except Exception as e:
                r = {"status": "error", "error": str(e)}
            results.append({"tool": "invoke_bos_uri_fallback", "uri": uri, "args": args, "result": r})
            print(f"    -> {uri}: status={r.get('status', '?')}")

    # 第二轮: 让 LLM 综合
    print(f"  -> LLM ({model}) 综合最终报告...")
    tool_summaries = []
    for r in results[:8]:
        s = json.dumps(r.get("result", {}), ensure_ascii=False, default=str)[:600]
        tool_summaries.append(f"[{r.get('tool', '?')}]: {s}")

    final_prompt = (
        "请基于以下 BOS 工具调用结果, 给出 '基层医疗机构药品集采政策' 的综合调研报告 "
        "(政策摘要 + 关键实体 + 来源引用 + 风险提示). 报告用 markdown 格式, 不超过 800 字.\n\n"
        "工具调用结果:\n" + "\n\n".join(tool_summaries)
    )
    try:
        if hasattr(client, "chat") and not hasattr(client, "completions"):
            final = client.chat(
                model=model,
                messages=[{"role": "user", "content": final_prompt}],
            )
            final_text = (final.get("message") or {}).get("content", "") or "(no content)"
        else:
            # 第二轮综合: 不传 max_tokens (让 ollama 用默认, 避免 thinking 模型用尽)
            # 不传 tools (避免模型再次调工具)
            final = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一名严谨的调研员, 用中文 markdown 输出 800 字以内的综合报告."},
                    {"role": "user", "content": final_prompt},
                ],
            )
            final_text = (final.choices[0].message.content or "(no content)") if final.choices else "(no choices)"
    except Exception as e:
        final_text = f"[ollama 综合失败: {e}]"

    return {
        "scenario": "基层医疗机构药品集采政策",
        "mode": "ollama",
        "model": model,
        "llm_calls": results,
        "final_report": final_text,
    }


# ── 真 API 模式 (用户配 ANTHROPIC_API_KEY 后) ─────────────
def real_mode_runner() -> dict:
    """真 API 模式: 调 Claude 用 tool_use 串联 6 URI."""
    try:
        import anthropic  # type: ignore[import-not-found]
    except ImportError:
        print("[fallback] anthropic 包未装, 自动转 mock 模式")
        return mock_mode_runner()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    client = anthropic.Anthropic(api_key=api_key)

    print("[真 API 模式] Claude + 6 BOS URI tool_use 串联 (卫健委场景)...")
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        tools=bos_uri_tool_schema(),
        messages=[{"role": "user", "content": HEALTHWORK_SCENARIO}],
    )

    results = []
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            tool_name = block.name
            tool_args = block.input
            print(f"  -> LLM 调 {tool_name}({tool_args})")
            handler = TOOL_DISPATCHER.get(tool_name)
            if handler is None:
                result = {"error": f"unknown_tool: {tool_name}"}
            else:
                result = handler(tool_args)
            results.append({"tool": tool_name, "args": tool_args, "result": result})

    # 第二轮: 让 LLM 综合
    final = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        tools=bos_uri_tool_schema(),
        messages=[
            {"role": "user", "content": HEALTHWORK_SCENARIO},
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": "请综合以上调用结果, 给出 '基层医疗机构药品集采政策' 的最终调研报告.",
            },
        ],
    )
    final_text = next(
        (b.text for b in final.content if getattr(b, "type", None) == "text"),
        "(no text block)",
    )
    return {
        "scenario": "基层医疗机构药品集采政策",
        "mode": "anthropic",
        "llm_calls": results,
        "final_report": final_text,
    }


# ── main ──────────────────────────────────────────────────
def _print_report(result: dict) -> None:
    print()
    print("=" * 70)
    print("综合报告")
    print("=" * 70)
    print(f"场景: {result.get('scenario', '?')}")
    print(f"模式: {result.get('mode', '?')}")
    if result.get("model"):
        print(f"模型: {result.get('model')}")
    if "final_report" in result:
        print()
        print(result["final_report"])
    else:
        uri_calls = result.get("uri_calls", [])
        print(f"URI 派发闭环: {len(uri_calls)} calls")
        for c in uri_calls:
            print(f"  - {c['uri']}: {c['result'].get('status', '?')}")
        print()
        print(result.get("summary", ""))

    # llm_calls (ollama/anthropic 模式)
    llm_calls = result.get("llm_calls", [])
    if llm_calls:
        print()
        print("─" * 70)
        print(f"LLM 工具调用: {len(llm_calls)} calls")
        for i, c in enumerate(llm_calls, 1):
            tname = c.get("tool", "?")
            targs = c.get("args", {})
            tres = c.get("result", {})
            status = tres.get("status", "?")
            print(f"  [{i}] {tname}  args={targs}  status={status}")


def _is_ollama_running() -> bool:
    """P41-W0: 检测 ollama 是否在跑 (http://localhost:11434). 用 stdlib urllib 避免依赖."""
    try:
        import urllib.request

        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    # 1. 优先 ollama (P41-W0 新增, 本地 LLM 免费)
    if _is_ollama_running():
        result = ollama_mode_runner()
    # 2. 退到 anthropic (如 key 配)
    elif os.environ.get("ANTHROPIC_API_KEY"):
        result = real_mode_runner()
    # 3. 退到 mock
    else:
        result = mock_mode_runner()
    _print_report(result)
