"""Unit tests for lib/yaml_utils.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib.yaml_utils import load_yaml, load_yaml_multi, load_yaml_or_default, write_yaml_atomic


class TestLoadYaml:
    def test_load_single_doc(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("name: test\nvalue: 42\n")
        data = load_yaml(f)
        assert data == {"name": "test", "value": 42}

    def test_load_list(self, tmp_path):
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n- item3\n")
        data = load_yaml(f)
        assert data == ["item1", "item2", "item3"]

    def test_load_empty(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        data = load_yaml(f)
        assert data is None

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_yaml(tmp_path / "nonexistent.yaml")

    def test_load_system_yaml(self):
        """Integration: load real system.yaml."""
        from lib.paths import SYSTEM_YAML
        data = load_yaml(SYSTEM_YAML)
        assert isinstance(data, dict)
        assert "current_phase" in data


class TestLoadYamlMulti:
    def test_multi_doc(self, tmp_path):
        f = tmp_path / "multi.yaml"
        f.write_text("---\nname: doc1\n---\nname: doc2\n---\nname: doc3\n")
        docs = load_yaml_multi(f)
        assert len(docs) == 3
        assert docs[0] == {"name": "doc1"}
        assert docs[1] == {"name": "doc2"}
        assert docs[2] == {"name": "doc3"}

    def test_single_doc_as_multi(self, tmp_path):
        f = tmp_path / "single.yaml"
        f.write_text("name: single\n")
        docs = load_yaml_multi(f)
        assert len(docs) == 1
        assert docs[0] == {"name": "single"}

    def test_empty_doc_filtered(self, tmp_path):
        f = tmp_path / "mixed.yaml"
        f.write_text("---\nname: real\n---\n\n---\nname: also_real\n")
        docs = load_yaml_multi(f)
        # yaml.safe_load_all returns None for empty docs
        assert len(docs) == 3  # includes None
        non_none = [d for d in docs if d is not None]
        assert len(non_none) == 2

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_yaml_multi(tmp_path / "nonexistent.yaml")


class TestWriteYamlAtomic:
    def test_write_and_read_back(self, tmp_path):
        f = tmp_path / "output.yaml"
        data = {"name": "test", "items": [1, 2, 3], "nested": {"key": "value"}}
        write_yaml_atomic(data, f)
        assert f.exists()
        loaded = load_yaml(f)
        assert loaded == data

    def test_overwrite(self, tmp_path):
        f = tmp_path / "overwrite.yaml"
        write_yaml_atomic({"v": 1}, f)
        write_yaml_atomic({"v": 2}, f)
        assert load_yaml(f) == {"v": 2}

    def test_no_tmp_left(self, tmp_path):
        f = tmp_path / "clean.yaml"
        write_yaml_atomic({"x": 1}, f)
        # Should not leave .tmp file
        assert not (tmp_path / "clean.yaml.tmp").exists()

    def test_preserve_unicode(self, tmp_path):
        f = tmp_path / "unicode.yaml"
        data = {"name": "测试", "desc": "中文内容"}
        write_yaml_atomic(data, f)
        loaded = load_yaml(f)
        assert loaded["name"] == "测试"
        assert loaded["desc"] == "中文内容"


class TestLoadYamlOrDefault:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "exists.yaml"
        f.write_text("key: value\n")
        data = load_yaml_or_default(f, {})
        assert data == {"key": "value"}

    def test_missing_file_returns_default(self, tmp_path):
        data = load_yaml_or_default(tmp_path / "missing.yaml", {"default": True})
        assert data == {"default": True}

    def test_missing_file_returns_none(self, tmp_path):
        data = load_yaml_or_default(tmp_path / "missing.yaml")
        assert data is None

    def test_empty_file_returns_none(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        data = load_yaml_or_default(f, {"fallback": True})
        assert data is None  # yaml.safe_load("") returns None
