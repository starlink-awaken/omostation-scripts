"""Unit tests for lib/ssot_checker.py."""
from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib.ssot_checker import SSOTChecker


class TestSSOTChecker:
    def test_no_errors_initially(self, tmp_path):
        c = SSOTChecker(root=tmp_path)
        assert not c.has_errors
        assert c.exit_code() == 0

    def test_require_text_present(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("This is a test document.\n")
        c = SSOTChecker(root=tmp_path)
        c.require_text("doc.md", "test document")
        assert not c.has_errors

    def test_require_text_absent(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("This is a document.\n")
        c = SSOTChecker(root=tmp_path)
        c.require_text("doc.md", "missing phrase")
        assert c.has_errors
        assert "missing" in c.errors[0]

    def test_require_text_file_not_found(self, tmp_path):
        c = SSOTChecker(root=tmp_path)
        c.require_text("nonexistent.md", "phrase")
        assert c.has_errors
        assert "not found" in c.errors[0]

    def test_require_text_with_label(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("content\n")
        c = SSOTChecker(root=tmp_path)
        c.require_text("doc.md", "missing", "my label")
        assert "my label" in c.errors[0]


class TestRequireAllText:
    def test_all_present(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("alpha beta gamma\n")
        c = SSOTChecker(root=tmp_path)
        c.require_all_text("doc.md", ("alpha", "beta", "gamma"))
        assert not c.has_errors

    def test_one_missing(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("alpha beta\n")
        c = SSOTChecker(root=tmp_path)
        c.require_all_text("doc.md", ("alpha", "beta", "gamma"))
        assert c.has_errors
        assert len(c.errors) == 1
        assert "gamma" in c.errors[0]

    def test_all_missing(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("content\n")
        c = SSOTChecker(root=tmp_path)
        c.require_all_text("doc.md", ("alpha", "beta"))
        assert len(c.errors) == 2


class TestForbidText:
    def test_not_present_ok(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("good content\n")
        c = SSOTChecker(root=tmp_path)
        c.forbid_text("doc.md", "forbidden")
        assert not c.has_errors

    def test_present_fails(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("has forbidden word\n")
        c = SSOTChecker(root=tmp_path)
        c.forbid_text("doc.md", "forbidden")
        assert c.has_errors
        assert "forbidden" in c.errors[0]

    def test_forbid_all_text(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("has bad1 and bad2\n")
        c = SSOTChecker(root=tmp_path)
        c.forbid_all_text("doc.md", ("bad1", "bad2"))
        assert len(c.errors) == 2


class TestRequireExists:
    def test_exists(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("content")
        c = SSOTChecker(root=tmp_path)
        c.require_exists("file.txt")
        assert not c.has_errors

    def test_not_exists(self, tmp_path):
        c = SSOTChecker(root=tmp_path)
        c.require_exists("missing.txt")
        assert c.has_errors

    def test_directory_exists(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        c = SSOTChecker(root=tmp_path)
        c.require_exists("subdir")
        assert not c.has_errors


class TestCheckTargets:
    def test_all_pass(self, tmp_path):
        (tmp_path / "a.md").write_text("required text\n")
        (tmp_path / "b.md").write_text("another text\n")
        c = SSOTChecker(root=tmp_path)
        c.check_targets({
            "a.md": ("required text",),
            "b.md": ("another text",),
        })
        assert not c.has_errors

    def test_some_fail(self, tmp_path):
        (tmp_path / "a.md").write_text("required text\n")
        (tmp_path / "b.md").write_text("wrong text\n")
        c = SSOTChecker(root=tmp_path)
        c.check_targets({
            "a.md": ("required text",),
            "b.md": ("expected text",),
        })
        assert c.has_errors
        assert len(c.errors) == 1


class TestCheckTargetsWithForbidden:
    def test_require_and_forbid_ok(self, tmp_path):
        (tmp_path / "doc.md").write_text("good phrase\n")
        c = SSOTChecker(root=tmp_path)
        c.check_targets_with_forbidden(
            {"doc.md": ("good phrase",)},
            forbidden=("bad phrase",),
        )
        assert not c.has_errors

    def test_forbidden_present(self, tmp_path):
        (tmp_path / "doc.md").write_text("good phrase and bad phrase\n")
        c = SSOTChecker(root=tmp_path)
        c.check_targets_with_forbidden(
            {"doc.md": ("good phrase",)},
            forbidden=("bad phrase",),
        )
        assert c.has_errors
        assert len(c.errors) == 1
        assert "forbidden" in c.errors[0]

    def test_require_missing_and_forbidden_present(self, tmp_path):
        (tmp_path / "doc.md").write_text("bad phrase\n")
        c = SSOTChecker(root=tmp_path)
        c.check_targets_with_forbidden(
            {"doc.md": ("required phrase",)},
            forbidden=("bad phrase",),
        )
        assert len(c.errors) == 2


class TestPrintReportAndExit:
    def test_pass_output(self, capsys, tmp_path):
        c = SSOTChecker(root=tmp_path)
        c.print_report()
        captured = capsys.readouterr()
        assert "PASS" in captured.out

    def test_fail_output(self, capsys, tmp_path):
        (tmp_path / "doc.md").write_text("content\n")
        c = SSOTChecker(root=tmp_path)
        c.require_text("doc.md", "missing")
        c.print_report()
        captured = capsys.readouterr()
        assert "FAIL" in captured.out
        assert "missing" in captured.out

    def test_exit_code_pass(self, tmp_path):
        c = SSOTChecker(root=tmp_path)
        assert c.exit_code() == 0

    def test_exit_code_fail(self, tmp_path):
        (tmp_path / "doc.md").write_text("content\n")
        c = SSOTChecker(root=tmp_path)
        c.require_text("doc.md", "missing")
        assert c.exit_code() == 1
