"""Tests for check-bulk-deletion.py — dual-metric bulk deletion gate."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "bin" / "gac" / "check-bulk-deletion.py"
)
_MODULE_NAME = "bin.check_bulk_deletion"
_SPEC = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
_module = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_NAME] = _module
_SPEC.loader.exec_module(_module)

_is_whitelisted = _module._is_whitelisted
_check_staged = _module._check_staged
DELETE_FILE_RATIO_THRESHOLD = _module.DELETE_FILE_RATIO_THRESHOLD
DELETE_LINE_THRESHOLD = _module.DELETE_LINE_THRESHOLD


# ── whitelist tests ────────────────────────────────────────


def test_whitelist_vendor_prefix():
    assert _is_whitelisted("vendor/foo/bar.py")
    assert _is_whitelisted("some/path/vendor/lib.py")


def test_whitelist_node_modules():
    assert _is_whitelisted("node_modules/react/index.js")


def test_whitelist_build_dirs():
    assert _is_whitelisted("dist/bundle.js")
    assert _is_whitelisted("build/output.o")
    assert _is_whitelisted("__pycache__/mod.cpython-311.pyc")


def test_whitelist_lock_files():
    assert _is_whitelisted("uv.lock")
    assert _is_whitelisted("package-lock.json")
    assert _is_whitelisted("yarn.lock")
    assert _is_whitelisted("poetry.lock")


def test_whitelist_pyc_suffix():
    assert _is_whitelisted("src/foo/bar.pyc")


def test_non_whitelisted_src_files():
    assert not _is_whitelisted("src/main.py")
    assert not _is_whitelisted("projects/aetherforge/src/gateway.py")
    assert not _is_whitelisted("tests/test_foo.py")
    assert not _is_whitelisted("README.md")


def test_whitelist_codebase_memory():
    assert _is_whitelisted(".codebase-memory/index.json")


# ── staged check with git repo ────────────────────────────


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    for i in range(20):
        (repo / f"file_{i}.py").write_text(f"x = {i}\n" * 100)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True
    )
    return repo


def test_no_deletion_passes(git_repo: Path):
    result = _check_staged(str(git_repo))
    assert not result["blocked"]
    assert result["deleted_files"] == 0


def test_small_deletion_below_threshold(git_repo: Path):
    for i in range(3):
        (git_repo / f"file_{i}.py").unlink()
    subprocess.run(["git", "add", "-A"], cwd=git_repo, capture_output=True, check=True)
    result = _check_staged(str(git_repo))
    assert not result["blocked"]


def test_bulk_deletion_blocks(git_repo: Path):
    for i in range(15):
        (git_repo / f"file_{i}.py").unlink()
    subprocess.run(["git", "add", "-A"], cwd=git_repo, capture_output=True, check=True)
    result = _check_staged(str(git_repo))
    assert result["deleted_files"] == 15
    assert result["deleted_lines"] > DELETE_LINE_THRESHOLD
    assert result["ratio"] >= DELETE_FILE_RATIO_THRESHOLD
    assert result["blocked"]


def test_whitelisted_deletion_not_counted(git_repo: Path):
    vendor = git_repo / "vendor"
    vendor.mkdir()
    for i in range(20):
        (vendor / f"lib_{i}.py").write_text("x = 1\n" * 100)
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add vendor"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )
    import shutil

    shutil.rmtree(vendor)
    subprocess.run(["git", "add", "-A"], cwd=git_repo, capture_output=True, check=True)
    result = _check_staged(str(git_repo))
    assert result["deleted_files"] == 0
    assert not result["blocked"]


def test_file_count_high_but_lines_low_not_blocked(git_repo: Path):
    for i in range(20):
        (git_repo / f"file_{i}.py").unlink()
    for i in range(20, 40):
        (git_repo / f"tiny_{i}.py").write_text("x\n")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add tiny"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )
    for i in range(20, 40):
        (git_repo / f"tiny_{i}.py").unlink()
    subprocess.run(["git", "add", "-A"], cwd=git_repo, capture_output=True, check=True)
    result = _check_staged(str(git_repo))
    assert result["deleted_files"] == 20
    assert result["deleted_lines"] < DELETE_LINE_THRESHOLD
    assert not result["blocked"]
