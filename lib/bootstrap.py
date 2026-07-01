"""bootstrap.py — workspace root 发现的唯一实现。

消除 40+ 处 Path(__file__).resolve().parents[N] 复制。
消除 Path.home() / "Workspace" 硬编码。

用法:
    from lib.bootstrap import workspace_root, omo_src_path
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def workspace_root() -> Path:
    """返回 workspace 根目录。

    发现顺序:
    1. WORKSPACE_ROOT 环境变量 (CI/容器友好)
    2. 从调用者栈推导 (scripts/ 的父目录)
    3. Path.home() / "Workspace" (最后手段, 仅本地)

    返回的路径一定存在 .omo/ 子目录 (否则报错)。
    """
    # 1. 环境变量
    env_root = os.environ.get("WORKSPACE_ROOT")
    if env_root:
        root = Path(env_root)
        if (root / ".omo").is_dir():
            return root

    # 2. 从 scripts/ 目录推导: scripts/ 的父目录就是 workspace root
    #    顶层脚本: __file__ = scripts/foo.py → parents[0] = scripts/
    #    omo/ 脚本: __file__ = scripts/omo/foo.py → parents[1] = scripts/
    here = Path(__file__).resolve().parent  # scripts/lib/
    scripts_dir = here.parent               # scripts/
    root = scripts_dir.parent               # workspace root

    if (root / ".omo").is_dir():
        return root

    # 3. 最后手段 (本地开发机)
    home_workspace = Path.home() / "Workspace"
    if (home_workspace / ".omo").is_dir():
        return home_workspace

    raise FileNotFoundError(
        f"无法定位 workspace root。"
        f"尝试了: WORKSPACE_ROOT={env_root}, {root}, {home_workspace}"
    )


def omo_src_path() -> Path:
    """返回 projects/omo/src 目录路径 (用于 sys.path.insert)。

    用法:
        from lib.bootstrap import setup_omo_src
        setup_omo_src()
        from omo.omo_io import write_yaml_atomic
    """
    return workspace_root() / "projects" / "omo" / "src"


def scripts_dir() -> Path:
    """返回 scripts/ 目录路径。"""
    return Path(__file__).resolve().parent.parent


def setup_omo_src(*extra: str | Path) -> None:
    """将 omo src 注入 sys.path, 供 L2 脚本 import omo.* 模块。

    消除 20+ 处 `sys.path.insert(0, str(omo_src_path()))` 重复。

    Args:
        *extra: 额外要注入的路径 (如 agora src, runtime src 等)
    """
    paths = [omo_src_path(), *extra]
    for p in paths:
        p = str(p)
        if p not in sys.path:
            sys.path.insert(0, p)
