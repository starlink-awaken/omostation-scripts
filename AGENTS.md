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
