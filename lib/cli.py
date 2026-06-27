"""cli.py — argparse 共享 base。

消除 16 个脚本各自的 argparse 初始化重复 + --omo-dir 参数重复。

用法:
    from lib.cli import BaseParser

    parser = BaseParser(description="My governance script")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    # args.omo_dir 已自动提供
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lib.paths import OMO_DIR


class BaseParser(argparse.ArgumentParser):
    """argparse base, 自动注入 --omo-dir 和 --workspace-root 参数。

    Attributes (after parse_args):
        omo_dir: Path — .omo/ 目录路径
        workspace_root: Path — workspace 根目录
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument(
            "--omo-dir",
            type=Path,
            default=OMO_DIR,
            help=f".omo/ 目录路径 (默认: {OMO_DIR})",
        )
        self.add_argument(
            "--workspace-root",
            type=Path,
            default=None,
            help="workspace 根目录 (默认: 自动发现)",
        )

    def parse_args(self, argv=None, namespace=None):
        args = super().parse_args(argv, namespace)
        # 如果 --workspace-root 指定了, 重新解析 omo_dir
        if args.workspace_root:
            args.omo_dir = args.workspace_root / ".omo"
        return args
