"""Unit tests for lib/cli.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib.cli import BaseParser


class TestBaseParser:
    def test_default_omo_dir(self):
        parser = BaseParser(description="test")
        args = parser.parse_args([])
        assert args.omo_dir is not None
        assert args.omo_dir.name == ".omo"

    def test_custom_omo_dir(self, tmp_path):
        parser = BaseParser(description="test")
        args = parser.parse_args(["--omo-dir", str(tmp_path)])
        assert str(args.omo_dir) == str(tmp_path)

    def test_workspace_root_override(self, tmp_path):
        # Create fake .omo
        (tmp_path / ".omo").mkdir()
        parser = BaseParser(description="test")
        args = parser.parse_args(["--workspace-root", str(tmp_path)])
        assert args.omo_dir == tmp_path / ".omo"

    def test_custom_args(self):
        parser = BaseParser(description="test")
        parser.add_argument("--verbose", action="store_true")
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True

    def test_custom_args_default(self):
        parser = BaseParser(description="test")
        parser.add_argument("--verbose", action="store_true")
        args = parser.parse_args([])
        assert args.verbose is False

    def test_help_does_not_crash(self, capsys):
        parser = BaseParser(description="my script")
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])
