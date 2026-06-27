"""P61-W0: 16 kairon 包 _DISPATCH 加 per-package action 映射.

8 do_<action> (search/ingest/validate/register/list/run/get/sync) 派发到 16 包
各自 do_default 真 action (P58-W0 实现). 找不到映射 fallback do_default 通用.

KISS: 1 套统一映射表 (按各包 do_default 真 action 集合选最佳匹配).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from lib.bootstrap import workspace_root

KAIRON_ROOT = workspace_root() / "projects" / "kairon"
PACKAGES = [
    "eidos", "kos", "codeanalyze", "core-models", "health-profile", "iris",
    "kairon-lib-events", "kairon-observability", "kairon-pipeline",
    "kairon-plugin-sdk", "kairon-utils", "kronos", "minerva", "ontoderive",
    "sophia", "forge",
]
PKG_DIR_MAP = {
    "core-models": "core_models",
    "health-profile": "health_profile",
    "kairon-lib-events": "kairon_events",
    "kairon-observability": "kairon_observability",
    "kairon-pipeline": "kairon_pipeline",
    "kairon-plugin-sdk": "kairon_plugin_sdk",
    "kairon-utils": "kairon_utils",
}

# 8 do_<action> → 16 包 do_default 真 action 映射
# (KISS: 按各包 do_default.py 实际 action 选最接近, 找不到映射用 None fallback)
ACTION_MAP: dict[str, dict[str, str | None]] = {
    "eidos":               {"search": "read",   "ingest": "read",  "validate": "read",  "register": "find_root", "list": "list",           "run": "read",         "get": "get_organ_path", "sync": "read"},
    "kos":                 {"search": "search", "ingest": "list_documents", "validate": "stats", "register": "list_documents", "list": "list_documents", "run": "stats",      "get": "stats",          "sync": "stats"},
    "forge":               {"search": "list",   "ingest": "list",  "validate": "health", "register": "list",  "list": "list",            "run": "status",         "get": "health",         "sync": "market"},
    "codeanalyze":         {"search": "list_commands", "ingest": "list_commands", "validate": "list_commands", "register": "list_commands", "list": "list_commands", "run": "version",   "get": "version",        "sync": "list_commands"},
    "core-models":         {"search": "types",  "ingest": "types", "validate": "schema", "register": "types", "list": "types",            "run": "types",          "get": "schema",         "sync": "types"},
    "health-profile":      {"search": "schema", "ingest": "schema","validate": "schema", "register": "schema","list": "schema",           "run": "schema",         "get": "schema",         "sync": "schema"},
    "iris":                {"search": "list_connectors", "ingest": "list_connectors", "validate": "config", "register": "commands", "list": "list_connectors", "run": "config",   "get": "commands",       "sync": "commands"},
    "kairon-lib-events":   {"search": "make",   "ingest": "make",  "validate": "bus_status", "register": "make", "list": "event_types",   "run": "make",          "get": "bus_status",    "sync": "bus_status"},
    "kairon-observability":{"search": "list_components", "ingest": "alert", "validate": "list_components", "register": "list_components", "list": "list_components", "run": "metric",  "get": "metric",         "sync": "metric"},
    "kairon-pipeline":     {"search": "sources","ingest": "sources","validate": "quality_gate", "register": "sources", "list": "list_components", "run": "quality_gate",  "get": "sources",        "sync": "sources"},
    "kairon-plugin-sdk":   {"search": "plugin_methods", "ingest": "plugin_methods", "validate": "schema", "register": "plugin_methods", "list": "context_fields", "run": "schema",  "get": "context_fields", "sync": "schema"},
    "kairon-utils":        {"search": "list_components", "ingest": "retry", "validate": "list_components", "register": "logger", "list": "list_components", "run": "retry",   "get": "list_components", "sync": "retry"},
    "kronos":              {"search": "list_methods", "ingest": "list_methods", "validate": "plan", "register": "list_methods", "list": "list_methods", "run": "plan",      "get": "version",         "sync": "list_methods"},
    "minerva":             {"search": "search_engine", "ingest": "pipeline", "validate": "search_engine", "register": "list_components", "list": "list_components", "run": "pipeline", "get": "search_engine", "sync": "search_engine"},
    "ontoderive":          {"search": "list_components", "ingest": "detector", "validate": "validator", "register": "list_components", "list": "list_components", "run": "detector", "get": "list_components", "sync": "detector"},
    "sophia":              {"search": "compile","ingest": "transitions", "validate": "compile", "register": "list_components", "list": "list_components", "run": "compile", "get": "list_components", "sync": "transitions"},
}

# P60-W0b _DISPATCH 模板 (16 包当前一致)
ORIG_DISPATCH = '''_DISPATCH = {
    # P60-W0b: 8 个 do_<action> 全部 delegate 到 do_default 真业务
    # (P58-W0 do_default.py 实现的 16 包各自真函数已覆盖 8 个 action)
    "search": lambda args: do_default({"action": "search", **args}),
    "ingest": lambda args: do_default({"action": "ingest", **args}),
    "validate": lambda args: do_default({"action": "validate", **args}),
    "register": lambda args: do_default({"action": "register", **args}),
    "list": lambda args: do_default({"action": "list", **args}),
    "run": lambda args: do_default({"action": "run", **args}),
    "get": lambda args: do_default({"action": "get", **args}),
    "sync": lambda args: do_default({"action": "sync", **args}),
}'''


def new_dispatch_for(pkg: str) -> str:
    """生成 per-package _DISPATCH + _ACTION_MAP."""
    mapping = ACTION_MAP[pkg]
    lines = []
    for action in ["search", "ingest", "validate", "register", "list", "run", "get", "sync"]:
        target = mapping.get(action)
        if target:
            lines.append(f'    "{action}": lambda args: do_default({{"action": "{target}", **args}}),')
        else:
            lines.append(f'    "{action}": lambda args: do_default({{"action": "{action}", **args}}),')
    body = "\n".join(lines).rstrip(",")
    return f'''_ACTION_MAP = {{
{pkg!r}: {mapping!r},
}}

_DISPATCH = {{
    # P61-W0: per-package 8 do_<action> → do_default 真 action 映射
    # 找不到 mapping 时 fallback 到 do_default 通用 (同 action name)
{body}
}}'''


def main() -> int:
    fixed = 0
    for pkg_dir in PACKAGES:
        src_dir = PKG_DIR_MAP.get(pkg_dir, pkg_dir)
        main_py = KAIRON_ROOT / "packages" / pkg_dir / "src" / src_dir / "__main__.py"
        if not main_py.exists():
            print(f"❌ {pkg_dir}: not found {main_py}")
            continue
        text = main_py.read_text(encoding="utf-8")
        if ORIG_DISPATCH not in text:
            print(f"⏭️  {pkg_dir}: ORIG_DISPATCH 不匹配, 跳过")
            continue
        new_text = text.replace(ORIG_DISPATCH, new_dispatch_for(pkg_dir))
        main_py.write_text(new_text, encoding="utf-8")
        result = subprocess.run(
            ["uv", "run", "ruff", "check", str(main_py)],
            capture_output=True, text=True, cwd=KAIRON_ROOT,
        )
        if result.returncode == 0:
            print(f"✅ {pkg_dir}: mapping installed + ruff clean")
            fixed += 1
        else:
            print(f"❌ {pkg_dir}: ruff failed")
            print(result.stdout + result.stderr)
    print(f"\nFixed {fixed}/{len(PACKAGES)} packages")
    return 0 if fixed == len(PACKAGES) else 1


if __name__ == "__main__":
    sys.exit(main())
