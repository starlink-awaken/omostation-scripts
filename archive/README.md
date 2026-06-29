# scripts/archive/

> 已归档脚本集合。这些脚本不再被 CI、Makefile、`.omo/_truth/`、`.omo/standards/` 或 `docs/` 引用，
> 仅作为 git 历史可追溯的归档保留，不再维护。

## 归档原因

随着 eCOS 架构收敛，一批历史脚本、演示脚本、一次性原型和已被取代的脚本不再参与日常治理流程。
把它们从顶层移到这里，可以：

1. 保持顶层 `scripts/` 整洁，减少新成员的认知负担
2. 避免 CI/Makefile 路径中混入无引用脚本
3. 保留完整历史，必要时可从 git 回溯

## 归档清单（共 29 个）

### Phase / 原型脚本

- `phase3_acceptance.py`
- `p60_refactor_dispatch.py`
- `p61_action_mapping.py`
- `p63_daemon_stdin.py`
- `p63_plist_smoke.sh`
- `p66_plist_retry.sh`

### 演示 / 场景脚本

- `demo-bos-system.py`
- `llm_bos_demo.py`
- `llm_healthwork_scenario.py`
- `scenario_budget_breaker.py`
- `scenario_deep_research.py`
- `scenario_evolution_loop.py`
- `scenario_great_search.py`
- `scenario_hitl_loop.py`
- `scenario_swarm_relay.py`
- `opc_p3_thin_binding_demo.py`
- `opc_p4_budget_audit_demo.py`

### 验证脚本

- `verify_ecos_v6_ssot.py`
- `verify_forensics.py`
- `verify_hardening.py`
- `verify_truth.py`

### 被取代脚本

- `check-port-registry.py` — 被 `check-vault-paths.py` 取代
- `gov_heartbeat.py` — 被 `omo_gov_heartbeat.py` 取代

### 历史工具脚本

- `agent_doc_review_check.sh`
- `cross_repo_stdio_smoke.py`
- `fix_missing_deliverables.py`
- `perf-bos-baseline.sh`
- `plot-metrics.py`
- `test-report.py`

## 使用约定

- 不要从 `archive/` 导入或调用这些脚本到活跃流程中
- 如需复活某个脚本，建议先复制回顶层并按当前 `lib/` 规范重构，而不是直接引用 `archive/`
- 新增归档脚本时，同步更新本 README 和顶层 `INDEX.md`
