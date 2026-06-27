"""Unit tests for lib/validators.py."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib.validators import (
    LintReport,
    require_text,
    require_exists,
    require_fields,
    require_list_min,
    match_pattern_list,
)


class TestLintReport:
    def test_empty_report(self):
        r = LintReport()
        assert not r.has_errors
        assert not r.has_warnings
        assert r.exit_code() == 0
        assert r.exit_code(strict=True) == 0

    def test_error(self):
        r = LintReport()
        r.err("file.yaml", "missing field")
        assert r.has_errors
        assert not r.has_warnings
        assert r.exit_code() == 1
        assert r.exit_code(strict=True) == 1

    def test_warning(self):
        r = LintReport()
        r.warn("file.yaml", "unusual status")
        assert not r.has_errors
        assert r.has_warnings
        assert r.exit_code() == 0
        assert r.exit_code(strict=True) == 1

    def test_ok(self):
        r = LintReport()
        r.ok("file.yaml", "all good")
        assert not r.has_errors
        assert not r.has_warnings
        assert r.exit_code() == 0

    def test_mixed(self):
        r = LintReport()
        r.ok("a.yaml", "ok")
        r.warn("b.yaml", "warn")
        r.err("c.yaml", "err")
        assert r.has_errors
        assert r.has_warnings
        assert r.exit_code() == 1
        assert len(r.errors) == 1
        assert len(r.warnings) == 1
        assert len(r.checks) == 1

    def test_print_summary(self, capsys):
        r = LintReport()
        r.err("file.yaml", "error msg")
        r.print_summary("Test Lint")
        captured = capsys.readouterr()
        assert "Test Lint" in captured.out
        assert "file.yaml" in captured.out
        assert "error msg" in captured.out
        assert "Errors: 1" in captured.out


class TestRequireText:
    def test_present(self):
        r = LintReport()
        require_text("hello world", "world", "test", r)
        assert not r.has_errors

    def test_absent(self):
        r = LintReport()
        require_text("hello world", "missing", "test", r)
        assert r.has_errors
        assert "missing" in r.errors[0][1]

    def test_empty_text(self):
        r = LintReport()
        require_text("", "needle", "test", r)
        assert r.has_errors


class TestRequireExists:
    def test_existing(self, tmp_path):
        r = LintReport()
        f = tmp_path / "exists.txt"
        f.write_text("content")
        require_exists(f, "test", r)
        assert not r.has_errors

    def test_missing(self, tmp_path):
        r = LintReport()
        require_exists(tmp_path / "missing.txt", "test", r)
        assert r.has_errors

    def test_directory(self, tmp_path):
        r = LintReport()
        d = tmp_path / "subdir"
        d.mkdir()
        require_exists(d, "test", r)
        assert not r.has_errors


class TestRequireFields:
    def test_all_present(self):
        r = LintReport()
        data = {"a": 1, "b": 2, "c": 3}
        require_fields(data, ["a", "b", "c"], "test", r)
        assert not r.has_errors

    def test_missing_field(self):
        r = LintReport()
        data = {"a": 1, "b": 2}
        require_fields(data, ["a", "b", "c"], "test", r)
        assert r.has_errors
        assert "c" in r.errors[0][1]

    def test_multiple_missing(self):
        r = LintReport()
        require_fields({}, ["a", "b"], "test", r)
        assert len(r.errors) == 2


class TestRequireListMin:
    def test_valid_list(self):
        r = LintReport()
        data = {"items": [1, 2, 3, 4]}
        result = require_list_min(data, "items", 3, "test", r)
        assert result == [1, 2, 3, 4]
        assert not r.has_errors

    def test_too_short(self):
        r = LintReport()
        data = {"items": [1]}
        result = require_list_min(data, "items", 3, "test", r)
        assert result is None
        assert r.has_errors

    def test_not_a_list(self):
        r = LintReport()
        data = {"items": "not a list"}
        result = require_list_min(data, "items", 3, "test", r)
        assert result is None
        assert r.has_errors

    def test_missing_key(self):
        r = LintReport()
        data = {}
        result = require_list_min(data, "items", 3, "test", r)
        assert result is None
        assert r.has_errors

    def test_exact_minimum(self):
        r = LintReport()
        data = {"items": [1, 2, 3]}
        result = require_list_min(data, "items", 3, "test", r)
        assert result == [1, 2, 3]
        assert not r.has_errors


class TestMatchPatternList:
    def test_all_match(self):
        r = LintReport()
        pattern = re.compile(r"^opc_\w+$")
        items = ["opc_test", "opc_foo", "opc_bar"]
        match_pattern_list(items, pattern, "signal", "test", r)
        assert not r.has_errors

    def test_some_dont_match(self):
        r = LintReport()
        pattern = re.compile(r"^opc_\w+$")
        items = ["opc_test", "invalid_name"]
        match_pattern_list(items, pattern, "signal", "test", r)
        assert r.has_errors
        assert "invalid_name" in r.errors[0][1]

    def test_empty_list(self):
        r = LintReport()
        pattern = re.compile(r"^opc_\w+$")
        match_pattern_list([], pattern, "signal", "test", r)
        assert not r.has_errors

    def test_non_string_item(self):
        r = LintReport()
        pattern = re.compile(r"^opc_\w+$")
        match_pattern_list([123], pattern, "signal", "test", r)
        assert r.has_errors
