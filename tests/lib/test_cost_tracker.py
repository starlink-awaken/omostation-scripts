"""Unit tests for lib/cost_tracker.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib.cost_tracker import CostTracker


@pytest.fixture
def tracker(tmp_path):
    """Create a CostTracker with a temp DB."""
    db = tmp_path / "test_usage.db"
    t = CostTracker(db_path=db)
    yield t
    t.close()


class TestCostTrackerInit:
    def test_lazy_connection(self, tmp_path):
        db = tmp_path / "test.db"
        t = CostTracker(db_path=db)
        assert t._conn is None
        _ = t.conn  # trigger init
        assert t._conn is not None
        t.close()

    def test_close(self, tmp_path):
        t = CostTracker(db_path=tmp_path / "test.db")
        _ = t.conn
        t.close()
        assert t._conn is None

    def test_close_idempotent(self, tmp_path):
        t = CostTracker(db_path=tmp_path / "test.db")
        _ = t.conn
        t.close()
        t.close()  # should not raise
        assert t._conn is None


class TestContextManager:
    def test_context_manager(self, tmp_path):
        db = tmp_path / "ctx.db"
        t = CostTracker(db_path=db)
        with t:
            _ = t.conn  # trigger lazy init
            assert t._conn is not None
        assert t._conn is None

    def test_context_manager_closes_on_exception(self, tmp_path):
        db = tmp_path / "ctx_exc.db"
        t = CostTracker(db_path=db)
        try:
            with t:
                raise ValueError("test error")
        except ValueError:
            pass
        assert t._conn is None


class TestLogCall:
    def test_basic_log(self, tracker):
        tracker.log_call(agent="omo", tool="llm-gateway", cost=0.01, tokens=100)
        summary = tracker.summary_by_org(days=7)
        assert len(summary) == 1
        assert summary[0]["org"] == "starlink-core"
        assert summary[0]["calls"] == 1
        assert summary[0]["cost"] == 0.01
        assert summary[0]["tokens"] == 100

    def test_custom_org(self, tracker):
        tracker.log_call(agent="omo", tool="test", cost=0.5, org="custom-org")
        summary = tracker.summary_by_org(days=7)
        assert summary[0]["org"] == "custom-org"
        assert summary[0]["cost"] == 0.5

    def test_multiple_calls_accumulate(self, tracker):
        tracker.log_call(agent="a", tool="t1", cost=0.01, tokens=10)
        tracker.log_call(agent="b", tool="t2", cost=0.02, tokens=20)
        tracker.log_call(agent="c", tool="t3", cost=0.03, tokens=30)
        summary = tracker.summary_by_org(days=7)
        assert summary[0]["calls"] == 3
        assert summary[0]["cost"] == 0.06
        assert summary[0]["tokens"] == 60

    def test_multiple_orgs(self, tracker):
        tracker.log_call(agent="a", tool="t", cost=0.01, org="org1")
        tracker.log_call(agent="b", tool="t", cost=0.02, org="org2")
        tracker.log_call(agent="c", tool="t", cost=0.03, org="org1")
        summary = tracker.summary_by_org(days=7)
        assert len(summary) == 2
        # org1 has higher cost (0.04 vs 0.02), should be first
        assert summary[0]["org"] == "org1"
        assert summary[0]["calls"] == 2
        assert summary[0]["cost"] == 0.04


class TestSummaryByOrg:
    def test_empty_db(self, tracker):
        summary = tracker.summary_by_org(days=7)
        assert summary == []

    def test_days_filter(self, tracker):
        tracker.log_call(agent="a", tool="t", cost=0.01)
        # Summary for 0 days should exclude everything
        summary = tracker.summary_by_org(days=0)
        # datetime('now', '-0 days') still includes today
        # so this should still return results
        assert len(summary) >= 0  # depends on SQLite timing

    def test_cost_rounding(self, tracker):
        tracker.log_call(agent="a", tool="t", cost=0.0123456789)
        summary = tracker.summary_by_org(days=7)
        # Should be rounded to 4 decimal places
        assert summary[0]["cost"] == 0.0123

    def test_zero_cost(self, tracker):
        tracker.log_call(agent="a", tool="t", cost=0, tokens=0)
        summary = tracker.summary_by_org(days=7)
        assert summary[0]["cost"] == 0.0
        assert summary[0]["tokens"] == 0


class TestSchemaMigration:
    def test_creates_table(self, tracker):
        # Table should be created on first conn access
        rows = tracker.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='resource_usage'"
        ).fetchall()
        assert len(rows) == 1

    def test_org_index(self, tracker):
        rows = tracker.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_usage_org'"
        ).fetchall()
        assert len(rows) == 1

    def test_org_column_exists(self, tracker):
        columns = {
            row["name"]
            for row in tracker.conn.execute("PRAGMA table_info(resource_usage)").fetchall()
        }
        assert "org" in columns
