# scripts/INDEX.md — 分类索引

> 全量脚本分类索引。新增脚本必须在此登记。
> 最后更新: 2026-06-27 (lib/ 9 模块同步 + gov_heartbeat.py 标记 deprecated)

## 1. CI 治理检查 (`check-*.py`) — 26 个

> 引用方: `.github/workflows/governance-check.yml` (18 个), 其他 CI workflows, Makefile, CLAUDE.md

| 脚本 | 引用方 | 用途 |
|------|--------|------|
| `check-cross-deps.py` | `cross-deps-enforce.yml`, `governance-check.yml` | 跨项目依赖方向校验 |
| `check-design-body-ssot.py` | `governance-check.yml` | DESIGN.md body SSOT 检查 |
| `check-design-history-ssot.py` | `governance-check.yml` | DESIGN.md 历史 SSOT 检查 |
| `check-design-risky-phrases.py` | `governance-check.yml` | DESIGN.md 风险用语检查 |
| `check-doc-ssot-snapshots.py` | `governance-check.yml` | 文档 SSOT 快照检查 |
| `check-governance-doc-ssot.py` | `governance-check.yml` | 治理文档 SSOT 检查 |
| `check-governance-guides-ssot.py` | `governance-check.yml` | 治理指南 SSOT 检查 |
| `check-governance-mechanism-ssot.py` | `governance-check.yml` | 治理机制 SSOT 检查 |
| `check-governance-surface-paths.py` | `governance-check.yml` | 治理面路径检查 |
| `check-index-coverage.py` | Makefile (`governance-index-check`) | INDEX.md 覆盖率检查 |
| `check-interfaces.py` | `interfaces-enforce.yml`, `governance-check.yml` | 接口契约 + 端口冲突检查 |
| `check-knowledge-history-ssot.py` | `governance-check.yml` | 知识面历史 SSOT 检查 |
| `check-knowledge-index-ssot.py` | `governance-check.yml` | 知识面索引 SSOT 检查 |
| `check-panorama-arch-links.py` | `governance-check.yml` | PANORAMA.md 架构链接检查 |
| `check-phase-closeout-ssot.py` | `governance-check.yml` | Phase 收口 SSOT 检查 |
| `check-plans-readme-ssot.py` | `governance-check.yml` | 计划 README SSOT 检查 |
| `check-project-arch-doc-contract.py` | `governance-check.yml` | 项目架构文档契约检查 |
| `check-project-arch-doc-ssot.py` | `governance-check.yml` | 项目架构文档 SSOT 检查 |
| `check-project-registry-ssot.py` | `governance-check.yml` | project-registry.yaml 一致性检查 |
| `check-ssot-reference-integrity.py` | `governance-check.yml` | SSOT 引用完整性检查 |
| `check-truth-inventory-routing.py` | `governance-check.yml` | 事实面 inventory 路由检查 |
| `check-truth-m1-governance-mapping.py` | `governance-check.yml` | M1 治理映射检查 |
| `check-vault-paths.py` | `mof-update.yml`, `port-registry-enforce.yml`, CLAUDE.md | 端口 + vault 路径硬编码检查 |

### CI 治理检查 (未被 CI 直接引用)

| 脚本 | 最后修改 | 用途 |
|------|---------|------|
| `check-future-annotations.py` | 2026-06-19 | `from __future__ import annotations` 使用检查 |
| `check-port-registry.py` | 2026-06-08 | 端口注册表检查 (可能被 `check-vault-paths.py` 取代) |
| `check-state-goals-alignment.py` | 2026-06-17 | state.yaml vs goals/current.yaml 对齐 (CI `state-goals-enforce.yml` 引用) |

## 2. OPC 自动化 (`opc_*`) — 19 个

> 引用方: `docs/ASYNC-BUS-CRON-HOOK-GOVERNANCE-DEEPDIVE.md` cron 调度表, `.omo/_truth/registry/mutation-surfaces.yaml`, `.omo/standards/task-yaml-rules.md`

### OPC cron 调度活跃脚本

| 脚本 | 引用方 | 用途 |
|------|--------|------|
| `opc_p1_memtheta_filter.py` | docs cron 表 | 记忆过滤 (每天 03:00) |
| `opc_p5_radar_cron.py` | docs cron 表 | 技术雷达 (周一 08:00) |
| `opc_p6_approval_board.py` | docs cron 表 | planned task 汇总 (每天 02:10) |
| `opc_p6_drift_detector.py` | docs cron 表 | 漂移检测 (每天 02:00) |
| `opc_p6_self_evolve.py` | docs cron 表, `.omo/_truth/registry/mutation-surfaces.yaml` | 漂移 → planned task (每天 02:05) |
| `opc_p6_weekly_loop.py` | docs cron 表 | 周循环逻辑 (周一 09:00) |
| `opc_p6_weekly_loop_cron.sh` | docs cron 表 | 周循环 cron wrapper |
| `opc_p6_self_evolve_cron.sh` | docs cron 表 | self-evolve cron wrapper |
| `opc_p7_doc_lint.py` | docs cron 表 | stale 证据检查 (每天 04:00) |
| `opc_p7_release_cycle.py` | docs cron 表 | 发布周期收口逻辑 |
| `opc_p7_release_cycle_cron.sh` | docs cron 表 | 发布周期 cron wrapper (周日 23:00) |
| `opc_mof_state_bridge_cron.sh` | docs cron 表 | mof-state-bridge cron wrapper |
| `opc_audit_rollout_5repos.py` | `.omo/standards/task-yaml-rules.md` | 5repos audit rollout |

### OPC 已收口/可能孤立

| 脚本 | 最后修改 | 用途 |
|------|---------|------|
| `opc_p3_thin_binding_demo.py` | 2026-06-18 | P3 thin binding 演示 |
| `opc_p4_budget_audit_demo.py` | docs opc | P4 budget audit 演示 |
| `opc_p7_audit_rollout_cron.sh` | 2026-06-12 | P7 audit rollout cron wrapper |
| `opc_p7_audit_rollout_daemon.py` | 2026-06-20 | P7 audit rollout daemon |
| `opc_p7_phase_gate_check.py` | 2026-06-25 | P7 phase gate 检查 |
| `opc_section17_metrics.py` | 2026-06-12 | §17 证据指标收集 |

## 3. X 轴治理检查 (`x1-x4-*.sh`) — 5 个

> 引用方: 根 Makefile (`governance-check` target), docs cron 表 (每天 09:00)

| 脚本 | 引用方 | 用途 |
|------|--------|------|
| `x1-audit-check.sh` | Makefile | X1 审计/边界检查 |
| `x2-staleness-check.sh` | Makefile | X2 新鲜度检查 |
| `x3-value-check.sh` | Makefile | X3 价值栈检查 |
| `x4-consistency-check.sh` | Makefile | X4 一致性检查 |
| `x1-x4-check.sh` | Makefile | X1-X4 全维度聚合检查 |

## 4. 治理工具 — 5 个

> 引用方: 根 Makefile, CI `debt-audit.yml`

| 脚本 | 引用方 | 用途 |
|------|--------|------|
| `debt-audit.sh` | Makefile (`debt-check`), `debt-audit.yml` | 债务审计 |
| `debt-leaderboard.sh` | Makefile (`debt-leaderboard`) | 债务排行榜 |
| `generate-governance-dashboard.py` | Makefile (`governance-dashboard`), docs cron 表 | 治理报告生成 |
| `generate-governance-data.py` | Makefile (`governance-data`), `debt-audit.yml` | 治理数据生成 |
| `governance-query.py` | Makefile (`governance-query`) | 治理查询 CLI |

## 5. OMO 状态同步 — 4 个

> 引用方: Makefile, `.omo/_truth/registry/mutation-surfaces.yaml`, `.omo/_truth/registry/agent-clis.yaml`, `.omo/tasks/README.md`

| 脚本 | 引用方 | 用途 |
|------|--------|------|
| `sync_omo_state.py` | Makefile (`governance-sync`), `.omo/_truth/`, `.omo/tasks/README.md` | OMO 状态同步 |
| `omo_gov_heartbeat.py` | 无直接引用 | OMO 治理心跳 (可能 cron 调用) |
| `gov_heartbeat.py` | [DEPRECATED] 无直接引用 | 治理心跳 (已废弃, 被 omo_gov_heartbeat.py 取代) |
| `omo_worker.py` | `.omo/_truth/registry/mutation-surfaces.yaml`, `.omo/tasks/README.md` | OMO worker 调度/分派/提升核心 |

## 6. SOP 脚本 — 2 个

> 引用方: `.omo/standards/MCP_STANDARDS.md`

| 脚本 | 引用方 | 用途 |
|------|--------|------|
| `sop_check_format_version.py` | `.omo/standards/MCP_STANDARDS.md` | MCP 文件格式版本检查 |
| `sop_precheck.py` | 无直接引用 | MCP pre-check (sop_check 的前置) |

## 7. CI/发布工具 — 3 个

| 脚本 | 引用方 | 用途 |
|------|--------|------|
| `ci_local.sh` | `.github/PULL_REQUEST_TEMPLATE.md`, `omostation-governance.yml` | 本地 CI 冒烟 |
| `release.sh` | `.omo/standards/task-yaml-rules.md` | 发布脚本 |
| `install-cron.sh` | docs cron 表 | cron 安装工具 |

## 8. 其他活跃脚本 — 3 个

| 脚本 | 最后修改 | 用途 |
|------|---------|------|
| `validate_protocol_registry.py` | 2026-06-06 | 协议注册表校验 (CI `meta-model-check.yml` 引用) |
| `lint-opc-carriers.py` | 2026-06-12 | OPC carriers lint |
| `health_scan.py` / `health_scan.sh` | 2026-06-24 | 健康扫描 (可能 runtime 项目引用) |

## 9. 历史/一次性脚本 — 29 个

> 以下脚本未被任何 CI/Makefile/.omo/docs 引用。保留作为历史记录。
> 如需清理，可在子模块 git 历史中回溯。

### Phase 一次性 (7)

| 脚本 | 最后修改 | 用途 |
|------|---------|------|
| `phase3_acceptance.py` | 2026-05-31 | Phase 3 验收 |
| `p60_refactor_dispatch.py` | 2026-06-08 | P60 重构分派 |
| `p61_action_mapping.py` | 2026-06-08 | P61 action 映射 |
| `p63_daemon_stdin.py` | 2026-06-08 | P63 daemon stdin |
| `p63_plist_smoke.sh` | 2026-06-08 | P63 plist 冒烟 |
| `p66_plist_retry.sh` | 2026-06-08 | P66 plist 重试 |
| `preserve-m1-files.sh` | 2026-06-07 | M1 文件保护 |

### Demo/场景脚本 (10)

| 脚本 | 最后修改 | 用途 |
|------|---------|------|
| `demo-bos-system.py` | 2026-06-07 | BOS 系统演示 |
| `llm_bos_demo.py` | 2026-06-07 | LLM BOS 演示 |
| `llm_healthwork_scenario.py` | 2026-06-07 | LLM 健康工作场景 |
| `scenario_budget_breaker.py` | 2026-06-16 | budget breaker 场景 |
| `scenario_deep_research.py` | 2026-06-16 | 深度研究场景 |
| `scenario_evolution_loop.py` | 2026-06-18 | 演化循环场景 |
| `scenario_great_search.py` | 2026-06-16 | 大搜索场景 |
| `scenario_hitl_loop.py` | 2026-06-18 | HITL 循环场景 |
| `scenario_swarm_relay.py` | 2026-06-18 | swarm relay 场景 |

### 阶段验证 (4)

| 脚本 | 最后修改 | 用途 |
|------|---------|------|
| `verify_ecos_v6_ssot.py` | 2026-06-17 | eCOS v6 SSOT 验证 |
| `verify_forensics.py` | 2026-06-17 | 取证验证 |
| `verify_hardening.py` | 2026-06-18 | 安全加固验证 |
| `verify_truth.py` | 2026-06-20 | 事实面验证 |

### 其他历史脚本 (8)

| 脚本 | 最后修改 | 用途 |
|------|---------|------|
| `test-report.py` | 2026-05-24 | 测试报告生成 |
| `plot-metrics.py` | 2026-06-20 | 指标绘图 |
| `cost_track_org.py` | 2026-06-03 | 成本跟踪 |
| `cross_repo_stdio_smoke.py` | 2026-06-08 | 跨仓 stdio 冒烟 |
| `fix_missing_deliverables.py` | 2026-06-13 | 修复缺失交付物 |
| `agent_doc_review_check.sh` | 2026-06-08 | Agent 文档审查检查 |
| `perf-bos-baseline.sh` | 2026-06-07 | BOS 性能基线 |
| `opc_section17_metrics.py` | 2026-06-12 | §17 指标 |

## 10. 子目录

| 目录 | 文件数 | 用途 |
|------|--------|------|
| `lib/` | 9 | 共享基础设施 (bootstrap, paths, yaml_utils, cli, validators, ssot_checker, cost_tracker, shell/common.sh) |
| `tests/` | 9 | 单元测试 (lib/ 7 模块 105 tests + omo/ 2 脚本) |
| `omo/` | 10 | OMO 治理脚本 (governance-agent.sh, omo_worker.py 78KB, x1/x2/x3 审计, cron 安装) |
| `shell/` | 9 | Shell 工具 (backup, restore, bridge install, watchdog, system consistency) |
| `install/` | 1 | 安装向导 (setup.sh) |

### omo/ 详细

| 文件 | 引用方 | 用途 |
|------|--------|------|
| `governance-agent.sh` | AGENTS.md (根), `.omo/_truth/mof-version.yaml` | 自治治理 agent (P72 改造) |
| `omo_worker.py` | `.omo/_truth/registry/mutation-surfaces.yaml`, `.omo/tasks/README.md` | worker 调度/分派/提升/回收核心 (78KB) |
| `cards_x3_metrics.py` | `.omo/_truth/x3-value-stack.yaml` | card_history SQLite 聚合 |
| `vault_x1_audit.py` | `.omo/_truth/x3-value-stack.yaml` | git content hash + author + age 跟踪 |
| `x2_freshness_audit.py` | (X2 新鲜度审计) | 新鲜度审计 |
| `install-*-cron.sh` (3) | (cron 安装) | dashboard/governance-agent/x2 cron 安装 |
| `omo-cleanup.sh` | (清理) | OMO 清理 |

### shell/ 详细

| 文件 | 引用方 | 用途 |
|------|--------|------|
| `daily-backup.sh` | `.omo/_truth/registry/projects-capabilities.yaml` | 每日备份 |
| `restore-from-backup.sh` | `.omo/_truth/registry/projects-capabilities.yaml` | 从备份恢复 |
| `check-system-consistency.sh` | `.omo/_truth/registry/projects-capabilities.yaml` | 系统一致性检查 |
| `install-all-bridges.sh` | (桥接安装) | 安装所有 bridges |
| `uninstall-all-bridges.sh` | (桥接卸载) | 卸载所有 bridges |
| `agora-watchdog.sh` | (监控) | agora 看门狗 |
| `fix-symlinks-to-wrappers.sh` | (修复) | 修复软链接 |
| `sync-omo-state.sh` | `.omo/_truth/registry/agent-clis.yaml`, `.omo/state/README.md` | OMO 状态同步 (shell wrapper) |
| `test-monitoring.sh` | (测试) | 监控测试 |

### install/ 详细

| 文件 | 用途 |
|------|------|
| `setup.sh` | 安装与配置向导 |

## 11. 共享基础设施 (`lib/`)

> scripts/ 作为独立 git 子模块, `lib/` 是正式 Python 子包, 为所有脚本提供共享基础设施。
> 新脚本强制使用 `lib/`, 旧脚本渐进迁移。当前 84/95 脚本已迁移 (88%)。

| 文件 | 暴露 API | 用途 |
|------|---------|------|
| `lib/__init__.py` | (package marker) | 包入口, 说明文档 |
| `lib/bootstrap.py` | `workspace_root()`, `omo_src_path()`, `scripts_dir()` | workspace root 发现 (统一 3 种模式 → 1 种) |
| `lib/paths.py` | `OMO_DIR`, `SYSTEM_YAML`, `TRUTH_DIR`, `BOS_SERVICES_YAML` 等 30+ 常量 | .omo/ 4-plane 路径常量 (消除 429 处硬编码) |
| `lib/yaml_utils.py` | `load_yaml()`, `load_yaml_multi()`, `write_yaml_atomic()`, `load_yaml_or_default()` | YAML 读写统一实现 (消除 3+ 套独立实现, 防多文档 bug) |
| `lib/cli.py` | `BaseParser` | argparse base, 自动注入 `--omo-dir` |
| `lib/validators.py` | `LintReport`, `require_text()`, `require_exists()`, `require_fields()`, `require_list_min()`, `match_pattern_list()` | lint 校验框架 (从 lint-opc-carriers.py 提取) |
| `lib/ssot_checker.py` | `SSOTChecker`, `require_text()`, `forbid_text()`, `check_targets()`, `check_targets_with_forbidden()` | SSOT 文档校验 (从 check-*-ssot.py 提取) |
| `lib/cost_tracker.py` | `CostTracker`, `log_call()`, `summary_by_org()` | SQLite 成本跟踪 (从 cost_track_org.py 提取, 支持 context manager) |
| `lib/shell/common.sh` | `pass()`, `warn()`, `fail()`, `info()`, `section()`, `exit_summary()`, `$REPO_ROOT`, `$OMO_DIR` | shell 共享: 颜色 helper + workspace 发现 + 输出格式 |

### 使用方式

```python
# Python 顶层脚本 (python3 scripts/foo.py, scripts/ 在 sys.path)
from lib.bootstrap import workspace_root
from lib.paths import OMO_DIR, SYSTEM_YAML
from lib.yaml_utils import load_yaml

system = load_yaml(SYSTEM_YAML)
```

```python
# Python omo/ 子目录脚本 (需先加 scripts/ 到 path)
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.bootstrap import workspace_root
```

```bash
# Shell 脚本
source "$(dirname "$0")/lib/shell/common.sh"
# 或从 omo/ 子目录:
source "$(dirname "$0")/../lib/shell/common.sh"
```
