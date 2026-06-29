#!/usr/bin/env python3
"""P6 self-evolution approval board thin wrapper."""
from __future__ import annotations


from lib.bootstrap import workspace_root, setup_omo_src

ROOT = workspace_root()
setup_omo_src()

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
