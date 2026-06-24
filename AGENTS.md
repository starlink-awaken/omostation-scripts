# AGENTS.md — omostation-scripts

> Omostation 工作站脚本集合 · OMO 治理 + Shell 工具 + 安装向导

## Quick Commands

```bash
# shellcheck 检查
find . -name '*.sh' -exec shellcheck {} +

# 查看可用脚本
ls -la omo/ shell/ install/
```

## 目录结构

```
scripts/
├── omo/        ── OMO 治理脚本（omo-cleanup, housekeeping）
├── shell/      ── Shell 工具脚本
└── install/    ── 安装与配置向导
```

## 桥接机制

作为子模块挂载在 `~/Workspace/scripts/`，通过 `~/.hermes/scripts/` 软链接桥接到 Hermes Agent。

### 规范

- Shell 脚本通过 shellcheck 检查
- 新增脚本需在 `.gitignore` 中添加排除规则
- 不包含运行时凭证或环境依赖
- `omo/` 目录下的脚本被 Hermes cron 调度

## Dependencies

无运行时依赖。所有脚本可独立运行，需 Bash。

## Workspace-Wide Governance (2026-06-24)

This project follows the workspace-level governance conventions documented in the root `AGENTS.md`:

- **Agent Mutation Protocol**: Any autonomous agent/cron/daemon that modifies workspace state must emit `agent_mutation_intent`, avoid direct file I/O to `.omo/`/`spaces/`, and commit immediately. See `.omo/standards/agent-mutation-protocol.md` for the full protocol.
- **SSOT Guardian**: Run `python3 bin/ssot-guardian.py` from the workspace root before committing to detect task-count, current-wave, submodule-pointer, or direct-omo-io drift.
- **direct-omo-io**: Scripts must route writes to `.omo/` through `omo CLI`, `projects/omo` core, or `projects/c2g` ingress — never via raw `open()/mkdir()/write_text()`.
- **Submodule Governance**: Commit changes inside the submodule first, then bump the root-repo pointer; `git submodule status` with a `+` prefix indicates pending drift.
