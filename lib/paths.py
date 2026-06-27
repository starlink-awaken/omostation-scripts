"""paths.py — .omo/ 4-plane 路径常量。

消除 429 处 .omo/ 路径字符串硬编码。

用法:
    from lib.paths import OMO_DIR, SYSTEM_YAML, TRUTH_DIR
"""

from __future__ import annotations

from pathlib import Path

from lib.bootstrap import workspace_root


# ── workspace ──
WORKSPACE = workspace_root()

# ── .omo/ 4 平面 ──
OMO_DIR = WORKSPACE / ".omo"
CONTROL_DIR = OMO_DIR / "_control"
TRUTH_DIR = OMO_DIR / "_truth"
KNOWLEDGE_DIR = OMO_DIR / "_knowledge"
DELIVERY_DIR = OMO_DIR / "_delivery"

# ── 状态 & 目标 ──
SYSTEM_YAML = OMO_DIR / "state" / "system.yaml"
HEALTH_YAML = OMO_DIR / "state" / "health.yaml"
GOALS_YAML = OMO_DIR / "goals" / "current.yaml"

# ── 任务 ──
TASKS_ACTIVE = OMO_DIR / "tasks" / "active"
TASKS_PLANNED = OMO_DIR / "tasks" / "planned"
TASKS_REGISTRY = OMO_DIR / "tasks" / "registry"

# ── 事实面注册表 ──
REGISTRY_DIR = TRUTH_DIR / "registry"
MUTATION_SURFACES = REGISTRY_DIR / "mutation-surfaces.yaml"
AGENT_CLIS = REGISTRY_DIR / "agent-clis.yaml"
PROJECTS_CAPABILITIES = REGISTRY_DIR / "projects-capabilities.yaml"
DIRECT_IO_BASELINE = REGISTRY_DIR / "direct-io-baseline.yaml"

# ── X 轴 ──
X1_POLICIES = TRUTH_DIR / "x1-governance-policies.yaml"
X2_FRESHNESS = TRUTH_DIR / "x2-freshness-rules.yaml"
X3_VALUE = TRUTH_DIR / "x3-value-stack.yaml"
X4_CONSISTENCY = TRUTH_DIR / "x4-consistency-rules.yaml"

# ── 知识面 ──
AUDITS_DIR = KNOWLEDGE_DIR / "audits"
DECISIONS_DIR = KNOWLEDGE_DIR / "decisions"

# ── 协议 ──
PROTOCOLS_DIR = WORKSPACE / "protocols"
PORT_REGISTRY = PROTOCOLS_DIR / "port-registry.yaml"
PORT_HARDCODE_BASELINE = PROTOCOLS_DIR / "port-hardcode-baseline.yaml"

# ── BOS 注册表 ──
BOS_SERVICES_YAML = WORKSPACE / "projects" / "agora" / "etc" / "bos-services.yaml"

# ── 项目注册表 ──
PROJECT_REGISTRY = WORKSPACE / "docs" / "project-registry.yaml"

# ── AppendOnlyLog 消费者路径 ──
GOVERNANCE_HISTORY = KNOWLEDGE_DIR / "governance-history.jsonl"
BOS_METRICS = KNOWLEDGE_DIR / "bos-metrics.jsonl"
OMO_EVENTS = KNOWLEDGE_DIR / "omo-events.jsonl"
OMO_ALERTS = KNOWLEDGE_DIR / "omo-alerts.jsonl"
OMO_SYNC_LOG = KNOWLEDGE_DIR / "omo-sync.jsonl"
OMO_TRAIL = KNOWLEDGE_DIR / "omo-trail.jsonl"

# ── runtime/ ──
RUNTIME_AUDIT_DIR = Path.home() / "runtime" / "audit"
GOVERNANCE_AUDIT_LOG = RUNTIME_AUDIT_DIR / "governance-audit.jsonl"
