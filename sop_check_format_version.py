#!/usr/bin/env python3
"""SOP: 检查 MCP Server 中 @mcp.tool() 函数的 format_version 合规性。

用法:
    python sop_check_format_version.py [文件或目录...]      # 默认从 convergence.yaml 动态发现
    python sop_check_format_version.py --json               # JSON 输出模式
    python sop_check_format_version.py --ci                 # CI 模式（JSON 输出 + 静默 stdout）

规则:
    每个 @mcp.tool() 装饰的函数返回的 dict 或 JSON 中必须包含 "format_version" 键。
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from lib.bootstrap import workspace_root
from lib.yaml_utils import load_yaml

# ── 已知的 MCP server 文件（默认回退，当 convergence.yaml 不存在时使用） ──
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
    """返回 workspace 根目录"""
    return workspace_root()


# ── B: 从 convergence.yaml 动态发现 MCP 文件 ──────────────────────


def _discover_from_convergence() -> list[str]:
    """从 gateway/scripts/convergence.yaml 动态发现 MCP server 文件列表。

    读取 projects 段的 entry_override / project_dir / pythonpath，
    自行解析出实际的 .py 文件路径。跳过 ignore 段中的项目。

    Returns:
        文件路径列表（workspace 相对路径字符串）。
    """
    ws = _find_workspace_root()
    yaml_path = ws / "projects" / "kairon" / "packages" / "gateway" / "scripts" / "convergence.yaml"

    if not yaml_path.exists():
        print(f"⚠  convergence.yaml 不存在 ({yaml_path}) — 使用 KNOWN_MCP_FILES 回退", file=sys.stderr)
        return KNOWN_MCP_FILES

    config = load_yaml(yaml_path)

    projects: dict = config.get("projects", {})
    ignore_set: set = set(config.get("ignore", []))
    discovered: set[str] = set()

    for name, cfg in projects.items():
        if name in ignore_set:
            continue

        # 确定项目根目录
        proj_dir = cfg.get("project_dir", name)
        proj_root = ws / proj_dir
        if not proj_root.exists():
            continue

        entry = cfg.get("entry_override", "")
        pythonpath = cfg.get("pythonpath", "")

        # 尝试解析 entry_override 为实际文件
        file_path = _resolve_entry(proj_root, entry, pythonpath)
        if file_path:
            discovered.add(str(file_path.relative_to(ws)))
            continue

        # 无 entry_override：扫描常见 MCP 文件名
        for candidate in ["mcp_server.py", "mcp.py"]:
            matches = list(proj_root.rglob(candidate))
            valid = [
                m for m in matches
                if "site-packages" not in m.parts and "node_modules" not in m.parts
            ]
            if valid:
                discovered.add(str(valid[0].relative_to(ws)))
                break

    # 补充 KNOWN_MCP_FILES 中未被 convergence.yaml 覆盖的文件
    # （如 SharedBrain 在 ignore 列表中）
    for kf in KNOWN_MCP_FILES:
        if kf not in discovered:
            p = ws / kf
            if p.exists():
                discovered.add(kf)

    return sorted(discovered)


def _resolve_entry(proj_root: Path, entry: str, pythonpath: str) -> Path | None:
    """将 entry_override 解析为实际文件路径。"""
    if not entry:
        return None

    if entry.endswith(".py"):
        # 直接文件路径
        direct = proj_root / entry
        if direct.exists():
            return direct
        # 带 pythonpath 前缀
        if pythonpath:
            alt = proj_root / pythonpath / entry
            if alt.exists():
                return alt
        return None

    # 模块路径：codeanalyze.mcp → 找 mcp.py
    module_parts = entry.split(".")
    for depth in range(len(module_parts), 0, -1):
        # 尝试 [pythonpath/] + module_path + rest_as_file
        rel_parts = module_parts[-depth:]
        candidate = proj_root / "/".join(rel_parts)
        if candidate.with_suffix(".py").exists():
            return candidate.with_suffix(".py")
        if candidate.exists() and candidate.is_dir():
            init = candidate / "__init__.py"
            if init.exists():
                return init

    # 扫描该模块最后部分
    last_part = module_parts[-1]
    matches = list(proj_root.rglob(f"{last_part}.py"))
    valid = [
        m for m in matches
        if "site-packages" not in m.parts and "node_modules" not in m.parts
    ]
    if valid:
        return valid[0]

    return None


# ── 核心检查函数 ────────────────────────────────────


def _gather_files(targets: list[str]) -> list[Path]:
    """收集要检查的文件列表"""
    ws = _find_workspace_root()
    files: list[Path] = []

    for t in targets:
        p = Path(t)
        if not p.exists():
            p = ws / t  # 尝试 workspace 相对路径
        if p.exists():
            if p.is_file():
                files.append(p.resolve())
            elif p.is_dir():
                files.extend(
                    f for f in p.rglob("*.py") if f.is_file() and "site-packages" not in f.parts
                )
        else:
            print(f"⚠  跳过文件（不存在）: {t}", file=sys.stderr)

    # 去重（避免同一文件被重复发现）
    seen: set[str] = set()
    unique: list[Path] = []
    for f in files:
        key = str(f.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def _find_helper_def(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """在 AST 中查找指定名称的辅助函数定义（如同文件内的 _ok/_error）。"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _has_format_version_in_helper(node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.AST) -> bool:
    """递归检查工具函数：如果它通过 return _ok(...) / return _error(...) 返回，
    则检查辅助函数的定义体中是否包含 format_version 字符串字面量。"""
    for child in ast.walk(node):
        # 匹配 return _ok(...) 或 return _error(...)
        if isinstance(child, ast.Return) and isinstance(child.value, ast.Call):
            call = child.value
            if isinstance(call.func, ast.Name) and call.func.id in ("_ok", "_error"):
                helper = _find_helper_def(tree, call.func.id)
                if helper:
                    # 检查辅助函数体是否包含 format_version
                    return any(
                        isinstance(n, ast.Constant) and isinstance(n.value, str)
                        and "format_version" in n.value
                        for n in ast.walk(helper)
                    )
    return False


def _check_py_file(filepath: Path) -> list[dict]:
    """检查一个 Python 文件的 format_version 合规性"""
    violations: list[dict] = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        return [{"file": str(filepath), "function": "<parse error>", "issue": f"SyntaxError: {e}"}]

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # 检查是否被 @mcp.tool() 装饰
        is_mcp_tool = any(
            isinstance(d, ast.Call) and _is_mcp_tool_call(d)
            for d in node.decorator_list
        )
        if not is_mcp_tool:
            continue

        function_name = node.name

        # 检查函数体中是否包含 "format_version" 字面量
        has_format_version = _has_format_version(node)

        # 如果工具函数本身没有 format_version，检查是否通过 _ok/_error 辅助函数委托
        helper_has_format_version = False
        if not has_format_version:
            helper_has_format_version = _has_format_version_in_helper(node, tree)
            if helper_has_format_version:
                pass

        if not has_format_version and not helper_has_format_version:
            violations.append({
                "file": str(filepath),
                "line": node.lineno,
                "function": function_name,
                "issue": "返回 dict/JSON 中缺少 format_version 字段",
            })

    return violations


def _is_mcp_tool_call(node: ast.Call) -> bool:
    """判断 ast.Call 是否是 mcp.tool() 调用"""
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "mcp"
        and node.func.attr == "tool"
    )


def _has_format_version(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """在函数体中递归搜索 format_version 字符串字面量"""
    for child in ast.walk(node):
        # 检查 Dict key: {"format_version": ...}
        if isinstance(child, ast.Dict):
            for key in child.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str) and "format_version" in key.value:
                    return True
        # 检查 result["format_version"] = ... 赋值
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Subscript):
                    if isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str) and "format_version" in target.slice.value:
                        return True
                    if isinstance(target.slice, ast.Index) and hasattr(target.slice, "value"):
                        val = target.slice.value
                        if isinstance(val, ast.Constant) and isinstance(val.value, str) and "format_version" in val.value:
                            return True
        # 检查 json.dumps({"format_version": ..., ...})
        if isinstance(child, ast.Call):
            for arg in child.args:
                if isinstance(arg, ast.Dict):
                    for key in arg.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str) and "format_version" in key.value:
                            return True
    return False


def _check_ts_file(filepath: Path) -> list[dict]:
    """检查 TypeScript MCP server 文件（粗略扫描）"""
    violations: list[dict] = []
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 简单行级扫描：找 async function 或 export function 但没有 format_version
    # 这是一个简化版本，完整 AST 解析需要 @typescript-eslint
    in_function = False
    function_name = ""
    function_start = 0
    has_format = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # 检测函数定义
        func_match = __import__("re").match(
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)", stripped
        )
        if func_match:
            if in_function and not has_format:
                violations.append({
                    "file": str(filepath),
                    "line": function_start,
                    "function": function_name,
                    "issue": "函数体可能缺少 format_version（粗略扫描）",
                })
            in_function = True
            function_name = func_match.group(1)
            function_start = i
            has_format = False
            continue

        if in_function:
            if "format_version" in stripped and not stripped.startswith("//"):
                has_format = True
            if stripped == "}" or stripped.startswith("}") and (
                i + 1 >= len(lines) or not lines[i].strip()
            ):
                if not has_format:
                    violations.append({
                        "file": str(filepath),
                        "line": function_start,
                        "function": function_name,
                        "issue": "函数体缺少 format_version",
                    })
                in_function = False

    if in_function and not has_format:
        violations.append({
            "file": str(filepath),
            "line": function_start,
            "function": function_name,
            "issue": "函数体缺少 format_version",
        })

    return violations


def _get_target_files(targets: list[str] | None) -> list[Path]:
    """获取要检查的文件列表：如有显式参数则使用，否则动态发现。"""
    if targets:
        return _gather_files(targets)

    # 默认模式：从 convergence.yaml 动态发现
    discovered = _discover_from_convergence()
    return _gather_files(discovered)


def main(targets: list[str] | None = None, json_output: bool = False) -> int:
    files = _get_target_files(targets)
    if not files:
        msg = "没有找到要检查的文件"
        if json_output:
            print(json.dumps({"error": msg, "files_checked": 0, "violations": [], "status": "error"}), file=sys.stderr)
        else:
            print(msg, file=sys.stderr)
        return 1

    all_violations: list[dict] = []
    checked_count = 0

    for fp in sorted(files):
        if fp.suffix == ".py":
            violations = _check_py_file(fp)
        elif fp.suffix == ".ts":
            violations = _check_ts_file(fp)
        else:
            continue

        checked_count += 1
        all_violations.extend(violations)

        if not json_output:
            if violations:
                print(f"\n❌ {fp.relative_to(_find_workspace_root())} — {len(violations)} 个问题")
                for v in violations:
                    print(f"   L{v['line']:4d}  {v['function']:30s}  {v['issue']}")
            else:
                print(f"✅ {fp.relative_to(_find_workspace_root())} — 通过")

    if json_output:
        # JSON 输出：标准输出放 JSON，标准错误放人类可读信息
        summary = {
            "files_checked": checked_count,
            "violation_count": len(all_violations),
            "status": "pass" if not all_violations else "fail",
            "violations": all_violations,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"检查完成: {checked_count} 个文件, {len(all_violations)} 个问题")
        print(f"状态: {'❌ 不合规' if all_violations else '✅ 全部合规'}")

    return 1 if all_violations else 0


if __name__ == "__main__":
    argv = sys.argv[1:]

    # 检查是否包含 --json 或 --ci 标志
    json_mode = "--json" in argv or "--ci" in argv
    ci_mode = "--ci" in argv

    # 去掉标志参数，只保留文件/目录参数
    targets_arg = [a for a in argv if a not in ("--json", "--ci")]

    if ci_mode:
        # CI 模式：完全静默，仅通过退出码通信（stdout JSON + stderr 静默）
        import contextlib
        import io

        with contextlib.redirect_stderr(io.StringIO()):
            result = main(targets_arg if targets_arg else None, json_output=True)
        sys.exit(result)
    elif json_mode:
        # JSON 模式：stderr 输出诊断，stdout 输出 JSON
        result = main(targets_arg if targets_arg else None, json_output=True)
        sys.exit(result)
    else:
        # 正常模式
        targets = targets_arg if targets_arg else None
        sys.exit(main(targets))
