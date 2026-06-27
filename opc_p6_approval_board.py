#!/usr/bin/env python3
"""P6 self-evolution approval board thin wrapper."""
from __future__ import annotations

import sys
from pathlib import Path

from lib.bootstrap import workspace_root, omo_src_path

ROOT = workspace_root()
sys.path.insert(0, str(omo_src_path()))

from omo.omo_approval_board import build_approval_board, write_approval_board


def build_board() -> dict:
    return build_approval_board(ROOT)


def write_board(board: dict):
    return write_approval_board(ROOT, board)


def main() -> int:
    board = build_approval_board(ROOT)
    json_path, md_path = write_approval_board(ROOT, board)
    print(f"# json: {json_path.relative_to(ROOT)}")
    print(f"# md: {md_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
