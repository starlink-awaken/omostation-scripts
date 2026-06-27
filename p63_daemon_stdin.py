"""P63-W0-D: 4 kairon 包 serve() 改传 daemon_mode=True (P63 helper 新参数).

P49-W0 helper run_stdio_dispatch 加 daemon_mode 参数, 4 包 (eidos/iris/kronos/ontoderive)
launchd 没 pipe stdin 需 daemon mode sleep + retry, 避免 KeepAlive 重启风暴.
12 包正常 call site 不动 (default daemon_mode=False 行为不变).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from lib.bootstrap import workspace_root

KAIRON_ROOT = workspace_root() / "projects" / "kairon"
PACKAGES = ["eidos", "iris", "kronos", "ontoderive"]
PKG_DIR_MAP = {
    "eidos": "eidos",
    "iris": "iris",
    "kronos": "kronos",
    "ontoderive": "ontoderive",
}

# 原模板 (P63-W0-D 错改的 stdin 检测段)
ORIG_SERVE_EIDOS = '''def serve() -> int:
    """P55-W0 serve 入口 (复用 kairon_utils.stdio_rpc).
    P63-W0-D: daemon 模式 stdin EOF 兼容 (launchd plist 没 pipe stdin).
    """
    import sys as _sys
    import time as _time

    from kairon_utils.stdio_rpc import run_stdio_dispatch  # type: ignore[import-not-found]

    # P57-W0: 自动 import 包内 do_default 真业务 (eidos.list_available_organs 等)
    try:
        from .do_default import do_default as _pkg_fn  # type: ignore[import-not-found]
        globals()["do_default"] = _pkg_fn
    except ImportError:
        pass

    # P63-W0-D: stdin EOF 检测 (launchd 没 pipe stdin) → daemon 模式 sleep + retry
    while True:
        if _sys.stdin.closed or not _sys.stdin.readable():
            print("[daemon] stdin closed (launchd mode), sleep 30s then retry", file=_sys.stderr, flush=True)
            _time.sleep(30)
            continue
        return run_stdio_dispatch(_call_action)'''

ORIG_SERVE_OTHERS = '''def serve() -> int:
    """P55-W0 serve 入口 (复用 kairon_utils.stdio_rpc).
    P63-W0-D: daemon 模式 stdin EOF 兼容 (launchd plist 没 pipe stdin).
    """
    import sys as _sys
    import time as _time
    from kairon_utils.stdio_rpc import run_stdio_dispatch  # type: ignore[import-not-found]

    # P63-W0-D: stdin EOF 检测 (launchd 没 pipe stdin) → daemon 模式 sleep + retry
    while True:
        if _sys.stdin.closed or not _sys.stdin.readable():
            print("[daemon] stdin closed (launchd mode), sleep 30s then retry", file=_sys.stderr, flush=True)
            _time.sleep(30)
            continue
        return run_stdio_dispatch(_call_action)'''

# 新模板: 传 daemon_mode=True 给 helper
NEW_SERVE_EIDOS = '''def serve() -> int:
    """P55-W0 serve 入口 (复用 kairon_utils.stdio_rpc).
    P63-W0-D: daemon_mode=True (launchd plist 没 pipe stdin, EOF sleep + retry).
    """
    from kairon_utils.stdio_rpc import run_stdio_dispatch  # type: ignore[import-not-found]

    # P57-W0: 自动 import 包内 do_default 真业务 (eidos.list_available_organs 等)
    try:
        from .do_default import do_default as _pkg_fn  # type: ignore[import-not-found]
        globals()["do_default"] = _pkg_fn
    except ImportError:
        pass

    return run_stdio_dispatch(_call_action, daemon_mode=True)'''

NEW_SERVE_OTHERS = '''def serve() -> int:
    """P55-W0 serve 入口 (复用 kairon_utils.stdio_rpc).
    P63-W0-D: daemon_mode=True (launchd plist 没 pipe stdin, EOF sleep + retry).
    """
    from kairon_utils.stdio_rpc import run_stdio_dispatch  # type: ignore[import-not-found]

    return run_stdio_dispatch(_call_action, daemon_mode=True)'''


def main() -> int:
    fixed = 0
    for pkg_dir in PACKAGES:
        src_dir = PKG_DIR_MAP[pkg_dir]
        main_py = KAIRON_ROOT / "packages" / pkg_dir / "src" / src_dir / "__main__.py"
        text = main_py.read_text(encoding="utf-8")
        orig = ORIG_SERVE_EIDOS if pkg_dir == "eidos" else ORIG_SERVE_OTHERS
        new = NEW_SERVE_EIDOS if pkg_dir == "eidos" else NEW_SERVE_OTHERS
        if orig not in text:
            print(f"⏭️  {pkg_dir}: ORIG 不匹配 (可能未错改, 跳过)")
            continue
        new_text = text.replace(orig, new)
        main_py.write_text(new_text, encoding="utf-8")
        result = subprocess.run(
            ["uv", "run", "ruff", "check", str(main_py)],
            capture_output=True, text=True, cwd=KAIRON_ROOT,
        )
        if result.returncode == 0:
            print(f"✅ {pkg_dir}: daemon_mode=True + ruff clean")
            fixed += 1
        else:
            print(f"❌ {pkg_dir}: ruff failed")
            print(result.stdout + result.stderr)
    print(f"\nFixed {fixed}/{len(PACKAGES)} packages")
    return 0 if fixed == len(PACKAGES) else 1


if __name__ == "__main__":
    sys.exit(main())
