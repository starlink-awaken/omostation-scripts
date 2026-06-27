# AGENTS.md — omostation-scripts

> Omostation 工作站脚本集合 (独立 git 子模块)
> 顶层 95 个脚本 + 4 个子目录。全量分类索引见 [INDEX.md](INDEX.md)。

## Quick Commands

```bash
# shellcheck 检查 (CI 同款)
find . -maxdepth 1 -name '*.sh' -exec shellcheck {} +

# 查看分类索引
cat INDEX.md

# 本地 CI 冒烟
bash ci_local.sh

# 测试 lib/ 共享层
python3 -c "from lib.bootstrap import workspace_root; print(workspace_root())"
```

## 目录结构

```
scripts/
├── lib/         ── 共享基础设施 (bootstrap, paths, yaml_utils, cli, shell/common.sh)
├── (顶层)      ── 95 个脚本, 按命名前缀分类 (见 INDEX.md)
├── omo/        ── OMO 治理脚本 (governance-agent, omo_worker, x1/x2/x3 审计)
├── shell/      ── Shell 工具 (backup, restore, bridge install, watchdog)
└── install/    ── 安装与配置向导 (setup.sh)
```

## 共享基础设施 (lib/)

`lib/` 是正式 Python 子包, 为所有脚本提供统一基础设施:

| 模块 | 用途 |
|------|------|
| `lib/bootstrap.py` | workspace root 发现 (统一 3 种模式 → 1 种) |
| `lib/paths.py` | .omo/ 4-plane 路径常量 |
| `lib/yaml_utils.py` | YAML 读写统一实现 |
| `lib/cli.py` | argparse base, 自动注入 --omo-dir |
| `lib/shell/common.sh` | shell 颜色 helper + REPO_ROOT + pass/warn/fail |

**新脚本强制使用 lib/, 旧脚本渐进迁移。**

## 引用约束

**脚本路径被以下位置硬编码引用，移动文件会 break CI**：

- 根 `Makefile`: 13 个脚本 (`scripts/x1-x4-*.sh`, `scripts/debt-*.sh`, `scripts/sync_omo_state.py` 等)
- `.github/workflows/governance-check.yml`: 18 个 `check-*.py` + `check-cross-deps.py` + `check-interfaces.py`
- `.github/workflows/`: 其他 workflow 引用 `check-vault-paths.py`, `check-state-goals-alignment.py`, `validate_protocol_registry.py` 等
- `.omo/_truth/registry/`: `mutation-surfaces.yaml`, `agent-clis.yaml`, `projects-capabilities.yaml` 等
- `docs/ASYNC-BUS-CRON-HOOK-GOVERNANCE-DEEPDIVE.md`: OPC cron 调度表引用 `opc_*.py/sh`
- `.github/PULL_REQUEST_TEMPLATE.md`: `ci_local.sh`

## 桥接机制

作为子模块挂载在 `~/Workspace/scripts/`，通过 `~/.hermes/scripts/` 软链接桥接到 Hermes Agent。

### 规范

- Shell 脚本通过 shellcheck 检查
- 新增脚本需在 [INDEX.md](INDEX.md) 登记分类
- 不包含运行时凭证或环境依赖
- `omo/` 目录下的脚本被 Hermes cron 调度
- 写入 `.omo/` 必须走 `omo CLI` / `projects/omo` / `projects/c2g` broker

## Dependencies

无运行时依赖。所有脚本可独立运行，需 Bash + Python 3.13+。

## Workspace-Wide Governance (2026-06-24)

This project follows the workspace-level governance conventions documented in the root `AGENTS.md`:

- **Agent Mutation Protocol**: Any autonomous agent/cron/daemon that modifies workspace state must emit `agent_mutation_intent`, avoid direct file I/O to `.omo/`/`spaces/`, and commit immediately. See `.omo/standards/agent-mutation-protocol.md` for the full protocol.
- **SSOT Guardian**: Run `python3 bin/ssot-guardian.py` from the workspace root before committing to detect task-count, current-wave, submodule-pointer, or direct-omo-io drift.
- **direct-omo-io**: Scripts must route writes to `.omo/` through `omo CLI`, `projects/omo` core, or `projects/c2g` ingress — never via raw `open()/mkdir()/write_text()`.
- **Submodule Governance**: Commit changes inside the submodule first, then bump the root-repo pointer; `git submodule status` with a `+` prefix indicates pending drift.
