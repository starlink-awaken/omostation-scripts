"""Unit tests for lib/bootstrap.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is on sys.path
SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib.bootstrap import workspace_root, omo_src_path, scripts_dir, setup_omo_src


class TestWorkspaceRoot:
    def test_returns_path_with_omo(self):
        root = workspace_root()
        assert (root / ".omo").is_dir()

    def test_env_var_override(self, monkeypatch, tmp_path):
        # Create a fake .omo dir
        fake_omo = tmp_path / ".omo"
        fake_omo.mkdir()
        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        root = workspace_root()
        assert root == tmp_path

    def test_env_var_invalid_falls_back(self, monkeypatch, tmp_path):
        # Point to a dir without .omo — should fall back to real workspace
        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        root = workspace_root()
        assert (root / ".omo").is_dir()


class TestOmoSrcPath:
    def test_returns_omo_src(self):
        p = omo_src_path()
        assert p.name == "src"
        assert p.parent.name == "omo"
        assert p.parent.parent.name == "projects"


class TestScriptsDir:
    def test_returns_scripts_dir(self):
        d = scripts_dir()
        assert d.name == "scripts"


class TestSetupOmoSrc:
    def test_injects_omo_src(self):
        # Save sys.path
        original = sys.path[:]
        try:
            # Remove omo src if present
            omo_src = str(omo_src_path())
            sys.path[:] = [p for p in sys.path if p != omo_src]
            assert omo_src not in sys.path

            setup_omo_src()
            assert omo_src in sys.path
        finally:
            sys.path[:] = original

    def test_idempotent(self):
        original = sys.path[:]
        try:
            setup_omo_src()
            count_before = sys.path.count(str(omo_src_path()))
            setup_omo_src()
            count_after = sys.path.count(str(omo_src_path()))
            assert count_before == count_after
        finally:
            sys.path[:] = original

    def test_extra_paths(self, tmp_path):
        original = sys.path[:]
        try:
            extra = tmp_path / "fake_src"
            setup_omo_src(extra)
            assert str(extra) in sys.path
        finally:
            sys.path[:] = original
