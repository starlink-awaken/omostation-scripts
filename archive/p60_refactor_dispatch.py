"""P60-W0b: 16 kairon 包 _DISPATCH 字典改成 delegate to do_default (1 surgical change per package).

替代方案: 不动 8 个 do_<action> 函数体 (避免 blanket sed 风险),
改 _DISPATCH 字典 8 行 (16 包 × 1 dict = 16 处 surgical change).

每改 1 包立即 ruff verify, 不批量无验证.
"""
from __future__ import annotations

import subprocess
import sys

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
ACTIONS = ["search", "ingest", "validate", "register", "list", "run", "get", "sync"]

# _DISPATCH 原模板 (P55-W0 era, 16 包完全一致):
ORIG_DISPATCH = '''_DISPATCH = {
    "search": do_search,
    "ingest": do_ingest,
    "validate": do_validate,
    "register": do_register,
    "list": do_list,
    "run": do_run,
    "get": do_get,
    "sync": do_sync,
    # 通用 fallback: 未知 action 试 do_default
}'''

# 新 _DISPATCH: 8 个 lambda delegate to do_default
# (避免 8 个 do_<action> 函数体反射式找不到真类的 P55-W0 时代 bug)
NEW_DISPATCH = '''_DISPATCH = {
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
            print(f"⏭️  {pkg_dir}: _DISPATCH 原模板不匹配, 跳过")
            continue
        new_text = text.replace(ORIG_DISPATCH, NEW_DISPATCH)
        main_py.write_text(new_text, encoding="utf-8")
        # ruff verify
        result = subprocess.run(
            ["uv", "run", "ruff", "check", str(main_py)],
            capture_output=True, text=True, cwd=KAIRON_ROOT,
        )
        if result.returncode == 0:
            print(f"✅ {pkg_dir}: fixed + ruff clean")
            fixed += 1
        else:
            print(f"❌ {pkg_dir}: ruff failed")
            print(result.stdout)
            print(result.stderr)
    print(f"\nFixed {fixed}/{len(PACKAGES)} packages")
    return 0 if fixed == len(PACKAGES) else 1


if __name__ == "__main__":
    sys.exit(main())
