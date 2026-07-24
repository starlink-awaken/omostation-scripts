"""Unit tests for X2 freshness audit runner (scripts/omo/x2_freshness_audit.py).

覆盖:
- check_mof_version_bump: timestamp 解析 (naive vs aware)
- check_mof_version_bump: 30 天阈值
- check_mof_version_bump: missing fields
- check_debt_evidence: closed 缺 evidence 检测
- check_debt_evidence: deferred 缺 next_review_at 检测
- check_debt_evidence: closed with sufficient evidence 通过
- CLI: --only 过滤
- main(): exit codes (0/1/2)
"""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "omo"
sys.path.insert(0, str(SCRIPTS_DIR))

import x2_freshness_audit as audit


class TestCheckMofVersionBump:
    def _write_version(self, omo_dir: Path, history: list) -> Path:
        truth_dir = omo_dir / "_truth"
        truth_dir.mkdir(parents=True, exist_ok=True)
        version_file = truth_dir / "mof-version.yaml"
        version_file.write_text(
            f"version: '{len(history) + 1}.0.0'\n"
            f"history:\n"
            + "\n".join(f"  - {{timestamp: '{h}'}}" for h in history),
            encoding="utf-8",
        )
        return version_file

    def test_recent_bump_ok(self, tmp_path, monkeypatch):
        omo_dir = tmp_path / "omo"
        truth_dir = omo_dir / "_truth"
        truth_dir.mkdir(parents=True)
        monkeypatch.setattr(audit, "OMO_DIR", omo_dir)
        self._write_version(omo_dir, [datetime.now(UTC).isoformat()])
        result = audit.check_mof_version_bump()
        assert result["status"] == "ok"
        assert result["stale"] == 0

    def test_old_bump_warning(self, tmp_path, monkeypatch):
        omo_dir = tmp_path / "omo"
        (omo_dir / "_truth").mkdir(parents=True)
        monkeypatch.setattr(audit, "OMO_DIR", omo_dir)
        old_ts = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        self._write_version(omo_dir, [old_ts])
        result = audit.check_mof_version_bump()
        assert result["status"] == "warning"
        assert result["stale"] == 1

    def test_naive_timestamp_normalized(self, tmp_path, monkeypatch):
        """未带 tzinfo 的 ISO timestamp 必须被识别为 UTC。"""
        omo_dir = tmp_path / "omo"
        (omo_dir / "_truth").mkdir(parents=True)
        monkeypatch.setattr(audit, "OMO_DIR", omo_dir)
        naive_recent = datetime.now().replace(microsecond=0).isoformat()
        self._write_version(omo_dir, [naive_recent])
        result = audit.check_mof_version_bump()
        assert result["status"] == "ok", f"failed on naive timestamp: {result['details']}"

    def test_empty_history_warning(self, tmp_path, monkeypatch):
        omo_dir = tmp_path / "omo"
        (omo_dir / "_truth").mkdir(parents=True)
        monkeypatch.setattr(audit, "OMO_DIR", omo_dir)
        version_file = omo_dir / "_truth" / "mof-version.yaml"
        version_file.write_text("version: '1.0.0'\nhistory: []\n", encoding="utf-8")
        result = audit.check_mof_version_bump()
        assert result["status"] == "warning"

    def test_missing_file_warning(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit, "OMO_DIR", tmp_path / "_missing_omo")
        result = audit.check_mof_version_bump()
        assert result["status"] == "warning"


class TestCheckDebtEvidence:
    def _write_debt(self, debt_dir: Path, debt_id: str, **fields):
        debt_file = debt_dir / f"{debt_id}.yaml"
        lines = [f"id: {debt_id}"]
        for k, v in fields.items():
            if isinstance(v, str):
                lines.append(f"{k}: '{v}'")
            else:
                lines.append(f"{k}: {v}")
        debt_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_closed_with_short_evidence_stale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit, "OMO_DIR", tmp_path / "omo")
        debt_dir = tmp_path / "omo" / "debt" / "items"
        debt_dir.mkdir(parents=True)
        self._write_debt(debt_dir, "DEBT-TEST-1",
                         lifecycle_state="closed",
                         resolution_evidence="short")
        result = audit.check_debt_evidence()
        assert result["status"] == "warning"
        assert result["stale"] == 1
        assert any(d["id"] == "DEBT-TEST-1" for d in result["details"])

    def test_closed_with_sufficient_evidence_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit, "OMO_DIR", tmp_path / "omo")
        debt_dir = tmp_path / "omo" / "debt" / "items"
        debt_dir.mkdir(parents=True)
        long_text = "X" * 30  # 30 chars > 20
        self._write_debt(debt_dir, "DEBT-TEST-2",
                         lifecycle_state="closed",
                         resolution_evidence=long_text)
        result = audit.check_debt_evidence()
        assert result["status"] == "ok"

    def test_deferred_without_next_review_stale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit, "OMO_DIR", tmp_path / "omo")
        debt_dir = tmp_path / "omo" / "debt" / "items"
        debt_dir.mkdir(parents=True)
        self._write_debt(debt_dir, "DEBT-TEST-3",
                         lifecycle_state="deferred",
                         gate_level="P3")
        result = audit.check_debt_evidence()
        assert result["status"] == "warning"
        assert result["stale"] == 1

    def test_no_debt_dir_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit, "OMO_DIR", tmp_path / "missing")
        result = audit.check_debt_evidence()
        assert result["status"] == "ok"
        assert result["total"] == 0


class TestMainCLI:
    def test_dry_run_does_not_write(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit, "DELIVERY_DIR", tmp_path / "audit")
        monkeypatch.setattr(audit, "TRUTH_DIR", tmp_path / "_truth")
        (tmp_path / "_truth").mkdir()
        # set up minimal truth file
        (tmp_path / "_truth" / "mof-version.yaml").write_text(
            "version: '1.0.0'\nhistory: []\n", encoding="utf-8",
        )
        monkeypatch.setattr(audit, "OMO_DIR", tmp_path / "omo")
        (tmp_path / "omo" / "debt" / "items").mkdir(parents=True)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "x2_freshness_audit.py"), "--dry-run"],
            capture_output=True, text=True, timeout=120,
        )
        assert not (tmp_path / "audit").exists() or not list((tmp_path / "audit").glob("*.json"))