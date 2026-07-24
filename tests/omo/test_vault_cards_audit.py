"""Unit tests for omo.vault_x1_audit and omo.cards_x3_metrics (P44 R0)."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "omo"  # tests/omo → scripts → scripts/omo
sys.path.insert(0, str(SCRIPTS_DIR))

# 让 module 路径可达
sys.path.insert(0, str(SCRIPTS_DIR.parent))


class TestVaultX1Audit:
    def test_content_hash_returns_16_chars(self, tmp_path):
        """content_hash 返回 SHA-256 前 16 字符"""
        from omo.vault_x1_audit import content_hash
        f = tmp_path / "test.md"
        f.write_text("# Hello", encoding="utf-8")
        h = content_hash(f)
        assert len(h) == 16
        # 同一内容, 同一 hash
        assert content_hash(f) == h

    def test_content_hash_different_content(self, tmp_path):
        from omo.vault_x1_audit import content_hash
        f1 = tmp_path / "a.md"
        f2 = tmp_path / "b.md"
        f1.write_text("AAA", encoding="utf-8")
        f2.write_text("BBB", encoding="utf-8")
        assert content_hash(f1) != content_hash(f2)

    def test_content_hash_missing_file(self, tmp_path):
        from omo.vault_x1_audit import content_hash
        assert content_hash(tmp_path / "missing.md") == "ERROR"

    def test_find_markdown_files_excludes_patterns(self, tmp_path):
        from omo.vault_x1_audit import find_markdown_files
        # Create test files in excluded paths
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "test.md").write_text("X")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "real.md").write_text("Y")
        files = find_markdown_files(tmp_path)
        names = [f.name for f in files]
        assert "real.md" in names
        assert "test.md" not in names

    def test_audit_vault_handles_no_git(self, tmp_path, monkeypatch):
        """无 git 历史时标记 no_git=True"""
        import omo.vault_x1_audit as vmod
        # 创建在 WORKSPACE_ROOT 内的子目录, 因为 audit_vault 强制 relative_to(WORKSPACE_ROOT)
        ws_subdir = vmod.WORKSPACE_ROOT / ".pytest_audit_tmp"
        ws_subdir.mkdir(exist_ok=True)
        md = ws_subdir / f"doc_{tmp_path.name}.md"
        md.write_text("# doc", encoding="utf-8")
        try:
            monkeypatch.setattr(vmod, "git_log_for_file", lambda *a, **kw: {})
            result = vmod.audit_vault(vmod.WORKSPACE_ROOT, days=90)
            # 找我们的 doc
            doc_results = [r for r in result["results"] if r["path"] == str(md.relative_to(vmod.WORKSPACE_ROOT))]
            assert len(doc_results) == 1
            assert doc_results[0]["no_git"] is True
        finally:
            md.unlink(missing_ok=True)
            ws_subdir.rmdir()

    def test_audit_vault_recent_file(self, tmp_path, monkeypatch):
        """有最近 commit 的文件 → stale=False"""
        import omo.vault_x1_audit as vmod
        ws_subdir = vmod.WORKSPACE_ROOT / ".pytest_audit_tmp"
        ws_subdir.mkdir(exist_ok=True)
        md = ws_subdir / f"fresh_{tmp_path.name}.md"
        md.write_text("# fresh", encoding="utf-8")
        try:
            monkeypatch.setattr(vmod, "git_log_for_file", lambda *a, **kw: {
                "commit": "abc1234",
                "author": "Test",
                "email": "t@e.com",
                "timestamp": int(datetime.now(UTC).timestamp()),
                "subject": "test",
            })
            result = vmod.audit_vault(vmod.WORKSPACE_ROOT, days=90)
            doc_results = [r for r in result["results"] if r["path"] == str(md.relative_to(vmod.WORKSPACE_ROOT))]
            assert len(doc_results) == 1
            assert doc_results[0]["stale"] is False
            assert doc_results[0]["age_days"] < 1
        finally:
            md.unlink(missing_ok=True)
            ws_subdir.rmdir()

    def test_audit_vault_old_file_stale(self, tmp_path, monkeypatch):
        """老文件 (180 天前) → stale=True (with 90 days threshold)"""
        import omo.vault_x1_audit as vmod
        ws_subdir = vmod.WORKSPACE_ROOT / ".pytest_audit_tmp"
        ws_subdir.mkdir(exist_ok=True)
        md = ws_subdir / f"old_{tmp_path.name}.md"
        md.write_text("# old", encoding="utf-8")
        try:
            monkeypatch.setattr(vmod, "git_log_for_file", lambda *a, **kw: {
                "commit": "old1234",
                "author": "Old",
                "email": "o@e.com",
                "timestamp": int((datetime.now(UTC) - timedelta(days=180)).timestamp()),
                "subject": "old commit",
            })
            result = vmod.audit_vault(vmod.WORKSPACE_ROOT, days=90)
            doc_results = [r for r in result["results"] if r["path"] == str(md.relative_to(vmod.WORKSPACE_ROOT))]
            assert len(doc_results) == 1
            assert doc_results[0]["stale"] is True
            assert doc_results[0]["age_days"] >= 180
        finally:
            md.unlink(missing_ok=True)
            ws_subdir.rmdir()

class TestCLIInvocation:
    """CLI 测试 — 用 sys.executable 但 cwd=WORKSPACE_ROOT (确保相对路径)"""

    def test_vault_cli_help(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "vault_x1_audit.py"), "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=str(SCRIPTS_DIR.parent.parent),
        )
        assert result.returncode == 0, f"stderr={result.stderr}"
        assert "Vault X1" in result.stdout

    def test_cards_cli_help(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cards_x3_metrics.py"), "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=str(SCRIPTS_DIR.parent.parent),
        )
        assert result.returncode == 0, f"stderr={result.stderr}"
        assert "CARDS X3" in result.stdout


class TestCardsX3Metrics:
    def _create_test_db(self, tmp_path) -> Path:
        """创建测试用 cards db"""
        db = tmp_path / "test_cards.db"
        with sqlite3.connect(str(db)) as conn:
            conn.execute("""
                CREATE TABLE cards (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    type TEXT,
                    created_at TEXT
                )
            """)
            now_iso = datetime.now(UTC).isoformat()
            old_iso = (datetime.now(UTC) - timedelta(days=60)).isoformat()
            for i, (status, type_, created) in enumerate([
                ("proposed", "idea", now_iso),
                ("active", "task", now_iso),
                ("done", "task", old_iso),
                ("archived", "research", old_iso),
            ]):
                conn.execute(
                    "INSERT INTO cards (id, status, type, created_at) VALUES (?, ?, ?, ?)",
                    (i + 1, status, type_, created),
                )
            # card_history 表 (X3 30-day active 用)
            conn.execute("""
                CREATE TABLE card_history (
                    id INTEGER PRIMARY KEY,
                    card_id INTEGER,
                    changed_at TEXT
                )
            """)
            conn.execute(
                "INSERT INTO card_history (card_id, changed_at) VALUES (?, ?)",
                (1, now_iso),
            )
        return db

    def test_collect_metrics_status_distribution(self, tmp_path):
        from omo.cards_x3_metrics import collect_metrics
        db = self._create_test_db(tmp_path)
        m = collect_metrics(db)
        assert m["card_count"] == 4
        assert m["status_distribution"]["proposed"] == 1
        assert m["status_distribution"]["active"] == 1
        assert m["status_distribution"]["done"] == 1
        assert m["status_distribution"]["archived"] == 1

    def test_collect_metrics_type_distribution(self, tmp_path):
        from omo.cards_x3_metrics import collect_metrics
        db = self._create_test_db(tmp_path)
        m = collect_metrics(db)
        assert m["type_distribution"]["idea"] == 1
        assert m["type_distribution"]["task"] == 2
        assert m["type_distribution"]["research"] == 1

    def test_collect_metrics_mean_age(self, tmp_path):
        from omo.cards_x3_metrics import collect_metrics
        db = self._create_test_db(tmp_path)
        m = collect_metrics(db)
        # 2 cards at 0 days + 2 cards at 60 days = avg 30 days
        assert 25 <= m["mean_age_days"] <= 35

    def test_collect_metrics_monthly_active(self, tmp_path):
        from omo.cards_x3_metrics import collect_metrics
        db = self._create_test_db(tmp_path)
        m = collect_metrics(db)
        # card_id=1 has card_history with now → active in 30 days
        assert m["monthly_active"] == 1

    def test_collect_metrics_missing_db(self, tmp_path):
        from omo.cards_x3_metrics import collect_metrics
        result = collect_metrics(tmp_path / "nonexistent.db")
        assert "error" in result
        assert "stale" in result

    def test_collect_metrics_no_cards_table(self, tmp_path):
        from omo.cards_x3_metrics import collect_metrics
        db = tmp_path / "empty.db"
        sqlite3.connect(str(db)).close()
        result = collect_metrics(db)
        # 0 cards, no error
        assert result["card_count"] == 0

    def test_find_card_db_returns_none_when_no_db(self, monkeypatch, tmp_path):
        import omo.cards_x3_metrics as cmod
        # monkeypatch Path.home to tmp_path
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        # clear DEFAULT_DB_PATHS resolution cache
        result = cmod.find_card_db()
        assert result is None or not result.exists()

    def test_cli_runs(self):
        """CLI --help 退出 0"""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cards_x3_metrics.py"), "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=str(SCRIPTS_DIR.parent.parent),
        )
        assert result.returncode == 0, f"stderr={result.stderr}"
        assert "CARDS X3" in result.stdout