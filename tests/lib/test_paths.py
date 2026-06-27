"""Unit tests for lib/paths.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib.paths import (
    WORKSPACE,
    OMO_DIR,
    CONTROL_DIR,
    TRUTH_DIR,
    KNOWLEDGE_DIR,
    DELIVERY_DIR,
    SYSTEM_YAML,
    GOALS_YAML,
    TASKS_ACTIVE,
    TASKS_PLANNED,
    REGISTRY_DIR,
    BOS_SERVICES_YAML,
    PROJECT_REGISTRY,
    PORT_REGISTRY,
)


class TestPathConstants:
    def test_workspace_is_valid(self):
        assert (WORKSPACE / ".omo").is_dir()

    def test_omo_dir_exists(self):
        assert OMO_DIR.is_dir()

    def test_4_plane_dirs(self):
        for d in (CONTROL_DIR, TRUTH_DIR, KNOWLEDGE_DIR, DELIVERY_DIR):
            assert d.is_dir(), f"{d} should exist"

    def test_system_yaml_exists(self):
        assert SYSTEM_YAML.is_file()
        assert SYSTEM_YAML.name == "system.yaml"

    def test_goals_yaml_exists(self):
        assert GOALS_YAML.is_file()
        assert GOALS_YAML.name == "current.yaml"

    def test_tasks_dirs(self):
        # tasks/active may not exist if no active tasks, but tasks/ should
        assert TASKS_ACTIVE.parent.is_dir()
        assert TASKS_PLANNED.is_dir()

    def test_registry_dir(self):
        assert REGISTRY_DIR.is_dir()

    def test_bos_services_yaml(self):
        assert BOS_SERVICES_YAML.is_file()

    def test_project_registry(self):
        assert PROJECT_REGISTRY.is_file()

    def test_port_registry(self):
        assert PORT_REGISTRY.is_file()

    def test_path_relationships(self):
        assert OMO_DIR.parent == WORKSPACE
        assert CONTROL_DIR.parent == OMO_DIR
        assert TRUTH_DIR.parent == OMO_DIR
        assert SYSTEM_YAML.parent == OMO_DIR / "state"
        assert GOALS_YAML.parent == OMO_DIR / "goals"
