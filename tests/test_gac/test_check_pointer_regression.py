"""Tests for check-pointer-regression.py — submodule pointer monotonicity."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "bin" / "gac" / "check-pointer-regression.py"
)
_MODULE_NAME = "bin.check_pointer_regression"
_SPEC = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
_module = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_NAME] = _module
_SPEC.loader.exec_module(_module)

_is_ancestor = _module._is_ancestor


@pytest.fixture
def repo_with_history(tmp_path: Path) -> Path:
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
    shas = []
    for i in range(3):
        (repo / f"file_{i}.py").write_text(f"x = {i}\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"commit {i}"],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        shas.append(out.stdout.strip())
    return repo, shas


def test_ancestor_detection(repo_with_history):
    repo, shas = repo_with_history
    cwd = str(repo)
    assert _is_ancestor(shas[0], shas[2], cwd=cwd)
    assert _is_ancestor(shas[1], shas[2], cwd=cwd)
    assert not _is_ancestor(shas[2], shas[0], cwd=cwd)


def test_same_sha_not_ancestor(repo_with_history):
    repo, shas = repo_with_history
    cwd = str(repo)
    assert _is_ancestor(shas[1], shas[1], cwd=cwd)
