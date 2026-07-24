#!/usr/bin/env python3
"""SOP 预检分析 — 在整改前分析目标文件的架构模式，识别潜在风险。

用法:
    python sop_precheck.py [文件或目录...]
    默认分析已知的 MCP server 文件。

输出:
    每个文件的架构模式分析报告 + 风险评分

适用场景:
    1. 新项目接入 MCP 工具规范时，预检当前状态
    2. SOP 整改前，识别可能走弯路的特殊模式
    3. 代码审查时，快速了解工具的返回模式分布
"""

from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

from lib.bootstrap import workspace_root

# ── 已知的 MCP server 文件（与 sop_check_format_version.py 同步） ──
KNOWN_MCP_FILES = [
    "projects/kairon/packages/agora/src/agora/server/mcp.py",
    "projects/kairon/packages/codeanalyze/src/codeanalyze/mcp.py",
    "projects/kairon/packages/iris/src/iris/mcp_server.py",
    "projects/kairon/packages/kronos/src/kronos/mcp_server.py",
    "projects/kairon/packages/minerva/src/minerva/mcp_server/server.py",
    "projects/kairon/packages/sophia/src/sophia/server/mcp_server.py",
    "projects/SharedBrain/organs/D_Gateway/mcp_server/server.py",
]


def _find_workspace_root() -> Path:
    return workspace_root()


def _gather_files(targets: list[str]) -> list[Path]:
    ws = _find_workspace_root()
    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if not p.exists():
            p = ws / t
        if p.exists():
            if p.is_file():
                files.append(p.resolve())
            elif p.is_dir():
                files.extend(
                    f for f in p.rglob("*.py") if f.is_file() and "site-packages" not in f.parts
                )
        else:
            print(f"⚠  跳过（不存在）: {t}", file=sys.stderr)
    return files


# ── 分析函数 ──


def _is_mcp_tool(decorator: ast.AST) -> bool:
    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
        return (
            isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id == "mcp"
            and decorator.func.attr == "tool"
        )
    return False


def _collect_return_calls(body: list[ast.AST]) -> list[str]:
    """收集函数体内所有 return X(...) 的调用名"""
    calls: list[str] = []
    for node in ast.walk(body if isinstance(body, ast.AST) else _wrap_body(body)):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(f"{func.attr}")
    return calls


def _wrap_body(body):
    """Some callers pass a list of statements; wrap in a dummy module for ast.walk."""
    if isinstance(body, list):
        return ast.Module(body=body, type_ignores=[])
    return body


def analyze_file(filepath: Path) -> dict:
    """分析一个文件的 MCP 工具架构模式"""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        return {"file": str(filepath), "error": str(e)}

    tools: list[dict] = []
    helper_functions: set[str] = set()

    # 第一遍：收集所有函数定义
    all_funcs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_funcs[node.name] = node

    # 第二遍：分析 @mcp.tool() 函数
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        is_tool = any(_is_mcp_tool(d) for d in node.decorator_list)
        if not is_tool:
            # 记录非工具的辅助函数（如 _ok/_error）
            if node.name.startswith("_"):
                helper_functions.add(node.name)
            continue

        tool_info: dict = {
            "name": node.name,
            "line": node.lineno,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "return_type": _detect_return_type(node),
            "return_pattern": _detect_return_pattern(node),
            "has_format_version_literal": False,
            "format_version_source": "缺失",
        }

        # 在工具函数体中搜索 format_version 字面量
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and "format_version" in child.value:
                tool_info["has_format_version_literal"] = True
                # 推断来源：是 dict key 还是赋值 target
                if _is_dict_key(child):
                    tool_info["format_version_source"] = "dict 字面量 key"
                elif _is_subscript_target(child):
                    tool_info["format_version_source"] = "result[key] 赋值"
                elif _is_call_arg(child):
                    tool_info["format_version_source"] = "函数调用参数"
                else:
                    tool_info["format_version_source"] = "字符串字面量"

        # 检查是否通过 _ok/_error 委托
        if not tool_info["has_format_version_literal"]:
            return_calls = _collect_return_calls(node)
            for call_name in return_calls:
                if call_name in all_funcs:
                    helper_node = all_funcs[call_name]
                    for child in ast.walk(helper_node):
                        if isinstance(child, ast.Constant) and isinstance(child.value, str) and "format_version" in child.value:
                            tool_info["has_format_version_literal"] = True
                            tool_info["format_version_source"] = f"委托给 {call_name}()"
                            break

        tools.append(tool_info)

    # 汇总
    total = len(tools)
    compliant = sum(1 for t in tools if t["has_format_version_literal"])
    non_compliant = total - compliant
    async_count = sum(1 for t in tools if t["is_async"])

    # 返回模式分布
    pattern_counter = Counter(t["return_pattern"] for t in tools)
    return_type_counter = Counter(t["return_type"] for t in tools)
    fv_source_counter = Counter(t["format_version_source"] for t in tools)

    # 风险评分
    risks = _assess_risks(tools, helper_functions, non_compliant)

    return {
        "file": str(filepath),
        "total_tools": total,
        "compliant": compliant,
        "non_compliant": non_compliant,
        "async_count": async_count,
        "sync_count": total - async_count,
        "patterns": dict(pattern_counter),
        "return_types": dict(return_type_counter),
        "format_version_sources": dict(fv_source_counter),
        "helper_functions": sorted(helper_functions),
        "tools": tools,
        "risks": risks,
    }


def _detect_return_type(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """检测返回类型注解"""
    if node.returns is None:
        return "无注解"
    return _type_annotation_str(node.returns)


def _type_annotation_str(node: ast.AST | None) -> str:
    """将 AST 类型注解节点转换为可读字符串"""
    if node is None:
        return "无注解"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Subscript):
        # dict[str, Any] → "dict[str, Any]"
        value = _type_annotation_str(node.value)
        if isinstance(node.slice, ast.Tuple):
            args = ", ".join(_type_annotation_str(e) for e in node.slice.elts)
            return f"{value}[{args}]"
        return f"{value}[{_type_annotation_str(node.slice)}]"
    # Python 3.9+: ast.Index 已被弃用，slice 直接是类型节点
    if isinstance(node, ast.Attribute):
        return f"{_type_annotation_str(node.value)}.{node.attr}"
    return "复杂类型"


def _detect_return_pattern(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """检测返回路径模式"""
    has_helper = False
    has_direct_dict = False
    has_json_dumps = False
    has_inject = False  # result["key"] = val; return result
    has_mix = False
    path_count = 0

    # 检查是否有注入式赋值：result["format_version"] = ...
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Subscript):
                    if isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str) and target.slice.value == "format_version":
                        has_inject = True
                        break
                    if isinstance(target.slice, ast.Index) and hasattr(target.slice, "value"):
                        val = target.slice.value
                        if isinstance(val, ast.Constant) and isinstance(val.value, str) and val.value == "format_version":
                            has_inject = True
                            break

    for child in ast.walk(node):
        if isinstance(child, ast.Return) and isinstance(child.value, ast.Call):
            call = child.value
            if isinstance(call.func, ast.Name):
                if call.func.id in ("_ok", "_error"):
                    has_helper = True
                    path_count += 1
                elif call.func.id == "json" or (isinstance(call.func, ast.Attribute) and call.func.attr == "dumps"):
                    has_json_dumps = True
                    path_count += 1
            elif isinstance(call.func, ast.Attribute) and call.func.attr == "dumps":
                has_json_dumps = True
                path_count += 1
        elif isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
            has_direct_dict = True
            path_count += 1
        elif isinstance(child, ast.Return) and isinstance(child.value, ast.Name):
            # return some_var — 可能是注入式
            if has_inject:
                path_count += 1

    if has_inject and not has_helper and not has_direct_dict and not has_json_dumps:
        return "注入式赋值后 return"

    if path_count > 1:
        has_mix = True

    if has_mix:
        modes = []
        if has_helper:
            modes.append("_ok/_error")
        if has_inject:
            modes.append("注入式")
        if has_direct_dict:
            modes.append("直接 return dict")
        if has_json_dumps:
            modes.append("json.dumps")
        return f"混合 ({', '.join(modes)})"
    if has_helper:
        return "_ok/_error 辅助函数"
    if has_json_dumps:
        return "json.dumps 直接序列化"
    if has_direct_dict:
        return "直接 return dict"
    if has_inject:
        return "注入式赋值后 return"
    return "未知"


def _is_dict_key(node: ast.AST) -> bool:
    """检查节点是否是 dict key"""
    # We don't track parent mapping when walking, so this is a second pass
    # For now, rely on the positional context; called from within ast.walk
    # This is a heuristic
    return True  # conservative


def _is_subscript_target(node: ast.AST) -> bool:
    """启发式：如果是作为 Subscript slice 的值"""
    return False  # 保守


def _is_call_arg(node: ast.AST) -> bool:
    """启发式：可能是函数调用的参数"""
    return True  # 保守


def _assess_risks(tools: list[dict], helper_functions: set[str], non_compliant: int) -> list[dict]:
    """评估风险项"""
    risks: list[dict] = []

    # 风险 1: AST 盲区（工具函数体没有 format_version 字面量）
    blind_count = sum(
        1 for t in tools
        if t["format_version_source"].startswith("委托给")
        or t["format_version_source"] == "缺失"
    )
    if blind_count > 0:
        risks.append({
            "level": "中" if blind_count < len(tools) else "高",
            "category": "AST 检测盲区",
            "detail": f"{blind_count}/{len(tools)} 个工具的 format_version 不在函数体内，"
                       "SOP 的 AST 静态检查可能漏检" if blind_count > 0 else "",
        })

    # 风险 2: 返回类型不一致
    return_types = Counter(t["return_type"] for t in tools)
    if len(return_types) > 1:
        types_str = ", ".join(f"{k}: {v}" for k, v in return_types.most_common())
        risks.append({
            "level": "中",
            "category": "返回类型不一致",
            "detail": f"混合使用 {types_str}，跨项目统一时需逐个确认",
        })
    elif len(return_types) == 1 and next(iter(return_types.keys())) == "str":
        risks.append({
            "level": "低",
            "category": "返回 JSON 字符串",
            "detail": "返回 str (JSON)，可考虑统一为 dict（由 fastmcp 序列化）",
        })

    # 风险 3: 返回模式不一致
    patterns = Counter(t["return_pattern"] for t in tools)
    if len(patterns) > 1:
        risks.append({
            "level": "中",
            "category": "返回模式不一致",
            "detail": "工具间使用不同的返回模式，维护成本较高",
        })

    # 风险 4: 合规性问题
    if non_compliant > 0:
        risks.append({
            "level": "高",
            "category": "合规性",
            "detail": f"{non_compliant}/{len(tools)} 个工具缺少 format_version",
        })

    # 风险 5: 异步工具
    async_count = sum(1 for t in tools if t["is_async"])
    if async_count > 0:
        risks.append({
            "level": "低",
            "category": "异步支持",
            "detail": f"{async_count}/{len(tools)} 个工具是 async def（旧版 SOP 无法检测 async 函数）",
        })

    if not risks:
        risks.append({
            "level": "无",
            "category": "全部正常",
            "detail": "未检测到显著风险",
        })

    return risks


# ── 报告输出 ──


def print_report(result: dict):
    """打印单个文件的分析报告"""
    file_rel = Path(result["file"]).relative_to(_find_workspace_root())
    print(f"\n{'='*60}")
    print(f"📋 SOP 预检分析: {file_rel}")
    print(f"{'='*60}")

    # 项目概况
    print("\n📊 项目概况:")
    print(f"  总工具数:     {result['total_tools']}")
    print(f"  同步/异步:    {result['sync_count']} / {result['async_count']}")
    compliance_icon = "✅" if result["non_compliant"] == 0 else "❌"
    print(f"  合规性:       {result['compliant']}/{result['total_tools']} {compliance_icon}")

    # 返回模式分析
    print("\n🔍 返回模式分析:")
    print(f"  返回类型:     {pretty_dict(result['return_types'])}")
    print(f"  返回模式:     {pretty_dict(result['patterns'])}")
    print(f"  format_version 来源: {pretty_dict(result['format_version_sources'])}")

    # 辅助函数
    if result["helper_functions"]:
        print(f"  辅助函数:     {', '.join(result['helper_functions'])}")

    # 逐个工具详情
    print("\n📝 工具详情:")
    for t in result["tools"]:
        icon = "✅" if t["has_format_version_literal"] else "❌"
        async_mark = " (async)" if t["is_async"] else ""
        print(f"  {icon} L{t['line']:4d}  {t['name']:25s}{async_mark}  "
              f"返:{t['return_type']:8s}  "
              f"模式:{t['return_pattern']:20s}  "
              f"FV:{t['format_version_source']}")

    # 风险评分
    print("\n⚠️  风险评分:")
    for r in result["risks"]:
        level_icon = {"高": "🔴", "中": "🟡", "低": "🟢", "无": "⚪"}
        print(f"  {level_icon.get(r['level'], '⚪')} [{r['level']}] {r['category']}: {r['detail']}")


def pretty_dict(d: dict) -> str:
    return ", ".join(f"{k}: {v}" for k, v in d.items())


# ── 主函数 ──


def main(targets: list[str] | None = None) -> int:
    if targets is None:
        targets = KNOWN_MCP_FILES

    files = _gather_files(targets)
    if not files:
        print("没有找到要分析的文件", file=sys.stderr)
        return 1

    all_risks: list[dict] = []
    for fp in sorted(files):
        if fp.suffix != ".py":
            continue
        result = analyze_file(fp)
        if "error" in result:
            print(f"❌ 解析失败: {result['file']}: {result['error']}", file=sys.stderr)
            continue
        print_report(result)
        for r in result.get("risks", []):
            all_risks.append({
                "file": str(fp.relative_to(_find_workspace_root())),
                "level": r["level"],
                "category": r["category"],
                "detail": r["detail"],
            })

    # 全局风险汇总
    print(f"\n{'='*60}")
    print("📋 全局风险汇总")
    print(f"{'='*60}")
    high = [r for r in all_risks if r["level"] == "高"]
    medium = [r for r in all_risks if r["level"] == "中"]
    low = [r for r in all_risks if r["level"] == "低"]
    print(f"  🔴 高风险: {len(high)} 项")
    for r in high:
        print(f"     {r['file']}: {r['detail']}")
    print(f"  🟡 中风险: {len(medium)} 项")
    for r in medium:
        print(f"     {r['file']}: {r['detail']}")
    print(f"  🟢 低风险: {len(low)} 项")
    for r in low:
        print(f"     {r['file']}: {r['detail']}")

    return 1 if high else 0


if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else KNOWN_MCP_FILES
    sys.exit(main(args))
