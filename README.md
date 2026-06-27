# omostation-scripts

> Omostation 工作站的运维脚本和自动化工具集合 (独立 git 子模块)。
> 顶层 95 个脚本 + 4 个子目录 (`lib/`, `omo/`, `shell/`, `install/`)。
> 全量分类索引见 [INDEX.md](INDEX.md)。

## 目录结构

```
scripts/
├── lib/         ── 共享基础设施 (bootstrap, paths, yaml_utils, cli, shell/common.sh)
├── omo/         ── OMO 治理脚本 (governance-agent, omo_worker, x1/x2/x3 审计)
├── shell/       ── Shell 工具 (backup, restore, bridge install, watchdog)
├── install/     ── 安装向导 (setup.sh)
└── (顶层 95 个脚本, 按前缀分类: check-*, opc_*, x1-x4-*, debt-*, scenario_* 等)
```

## 用法

作为子模块挂载在 `~/Workspace/scripts/` 下：

```bash
cd ~/Workspace
git submodule update --init scripts/
```

## 共享基础设施 (lib/)

新增脚本强制使用 `lib/` 共享层，旧脚本渐进迁移：

```python
# Python
from lib.bootstrap import workspace_root
from lib.paths import OMO_DIR, SYSTEM_YAML
from lib.yaml_utils import load_yaml
```

```bash
# Shell
source "$(dirname "$0")/lib/shell/common.sh"
```

详见 [INDEX.md](INDEX.md) §11。

## 引用方

这些脚本被以下位置直接引用，**移动文件路径会 break CI**：

| 引用方 | 引用方式 | 示例 |
|--------|---------|------|
| **Makefile** (根) | target 调用 | `scripts/debt-audit.sh`, `scripts/x1-x4-check.sh` |
| **CI workflows** | `.github/workflows/*.yml` | `governance-check.yml` 引用 18 个 `check-*.py` |
| **.omo/_truth/** | 注册表 entrypoint | `mutation-surfaces.yaml` 引用 `omo_worker.py` |
| **.omo/standards/** | 文档引用 | `MCP_STANDARDS.md` 引用 `sop_check_format_version.py` |
| **docs/** | cron 表 + 说明 | `ASYNC-BUS-CRON-HOOK-GOVERNANCE-DEEPDIVE.md` cron 调度表 |
| **CLAUDE.md** (根) | 治理机制说明 | `check-vault-paths.py --check-ports` |
| **PULL_REQUEST_TEMPLATE** | 本地 CI 入口 | `./scripts/ci_local.sh` |

## 治理

- Shell 脚本需通过 shellcheck 检查 (CI `ci-lint.yml` 自动跑)
- 新增脚本需在 [INDEX.md](INDEX.md) 登记分类
- 不包含运行时凭证或环境依赖
- 写入 `.omo/` 必须走 `omo CLI` / `projects/omo` / `projects/c2g` broker，禁止 direct file I/O

## 层位置

跨层运维工具，不归属于任一 eCOS 层。通过 Hermes cron 和 cron-service 调度。
