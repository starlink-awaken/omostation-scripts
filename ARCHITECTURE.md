# ARCHITECTURE.md — omostation-scripts

> **scripts/** 独立 git 子模块 · omostation 工作站横切工具层
> 版本: v1.1 | 2026-06-29
> 全量脚本索引: [INDEX.md](INDEX.md) | 开发规范: [AGENTS.md](AGENTS.md)

---

## 1. 定位

scripts/ 是 omostation 工作站的**横切工具层** (Cross-Cutting Tooling Layer)。

- **不归属于 5+4+1+1 任一架构层**，跨层服务
- **被 CI / Makefile / cron / .omo 注册表 / docs 直接引用**，路径不可随意移动
- **唯一运行时依赖**: `projects/omo/src` (通过 `lib/bootstrap.omo_src_path()` 注入)
- **作为独立 git 子模块**存在，有自己的版本历史和 CI

```
omostation workspace
├── projects/          ← 17 个架构层项目 (L0-L4, I0, M0, X)
├── .omo/              ← 治理核心 (4 plane: control/truth/knowledge/delivery)
├── bin/               ← 工作区 CLI 入口 (workspace, verify, register-mcp...)
├── scripts/           ← 本项目: 横切工具层
│   ├── lib/           ← L0 共享基础设施
│   ├── (72 scripts)   ← L1/L2 功能域脚本
│   ├── omo/           ← OMO 治理脚本子目录
│   ├── shell/         ← Shell 运维工具子目录
│   ├── install/       ← 安装向导子目录
│   └── archive/       ← 已归档脚本子目录
└── .github/workflows/ ← CI 定义 (引用 scripts/check-*.py 等)
```

---

## 2. 架构原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | **平铺保持** | 72 个活跃脚本平铺在顶层，CI/Makefile 路径不断。分类靠命名前缀，不靠子目录；23 个历史脚本移至 archive/ |
| 2 | **lib/ 唯一共享源** | 所有共享代码在 `lib/`。禁止在脚本间互相 import (omo_worker 例外) |
| 3 | **命名即分类** | `check-*` = CI 门禁, `opc_*` = cron 自动化, `x[1-4]-*` = X 轴审计, 以此类推 |
| 4 | **依赖单向** | `脚本 → lib → (可选) projects/omo/src`。禁止反向依赖 |
| 5 | **脚本独立** | 每个脚本是独立入口，不 import 其他脚本 (omo_worker 例外) |
| 6 | **新脚本强制 lib/** | 新脚本必须用 `lib/bootstrap` + `lib/paths`，旧脚本渐进迁移 |

---

## 3. 分层模型

```
┌─────────────────────────────────────────────────────────────┐
│  L2  OMO 耦合层                                               │
│  需要 sys.path.insert(projects/omo/src) 的脚本               │
│  sync_omo_state · opc_p6_self_evolve · opc_p7_* · omo_worker│
│  (~12 个)                                                    │
├─────────────────────────────────────────────────────────────┤
│  L1  Workspace 感知层                                         │
│  依赖 workspace root / .omo 路径，但不依赖 omo src            │
│  check-*.py · x[1-4]-*.sh · debt-*.sh · governance-* · etc. │
│  (~60 个)                                                    │
├─────────────────────────────────────────────────────────────┤
│  L0  共享基础设施层                                            │
│  lib/bootstrap.py · lib/paths.py · lib/yaml_utils.py        │
│  lib/cli.py · lib/validators.py · lib/ssot_checker.py      │
│  lib/cost_tracker.py · lib/shell/common.sh                  │
│  (9 个模块)                                                   │
└─────────────────────────────────────────────────────────────┘
```

### 层间规则

| 规则 | 说明 |
|------|------|
| L0 不依赖 L1/L2 | lib/ 只用 stdlib + PyYAML，不 import 任何脚本 |
| L1 只依赖 L0 | 用 `lib/bootstrap` + `lib/paths`，不做 `sys.path.insert` |
| L2 依赖 L0 + omo src | 先 `lib/bootstrap.omo_src_path()` 再 `sys.path.insert` |
| 禁止 L1 → L2 | check-*.py 不能 import opc_* 或 sync_* |
| 禁止脚本互引 | 唯一例外: omo_worker.py (历史原因) |

---

## 4. 功能域模型

scripts/ 的 72 个活跃脚本按业务能力划分为 **6 个功能域**：

```
┌──────────────────────────────────────────────────┐
│              scripts/ 功能域 (72 scripts)          │
├──────────┬──────────┬──────────┬─────────────────┤
│ CI Gates │ OPC Auto │ X-Axis   │ Governance Tools│
│ 25       │ 17       │ 5        │ 4               │
├──────────┼──────────┼──────────┼─────────────────┤
│ OMO Sync │ SOP/Util │          │                 │
│ 3        │ 18       │          │                 │
└──────────┴──────────┴──────────┴─────────────────┘
```

> 另有 `archive/` 子目录保存 23 个已归档的历史/演示/废弃脚本，不再被 CI/Makefile/.omo/docs 引用。

### 功能域详情

| 域 | 前缀 | 数量 | 层 | 入口 | 依赖 |
|----|------|------|----|------|------|
| **CI Gates** | `check-*.py` | 25 | L1 | `.github/workflows/governance-check.yml` | lib/paths, lib/yaml_utils |
| **OPC Automation** | `opc_*` | 17 | L2 | cron schedule (docs ASYNC-BUS-CRON) | lib/bootstrap, projects/omo/src |
| **X-Axis Audit** | `x[1-4]-*` | 5 | L1 | Makefile (`governance-check`) | lib/shell/common.sh |
| **Governance Tools** | `debt-*`, `governance-*` | 4 | L1 | Makefile, CI `debt-audit.yml` | lib/shell/common.sh, lib/paths |
| **OMO State Sync** | `sync_*`, `omo_*` | 3 | L2 | Makefile (`governance-sync`), .omo/_truth | lib/bootstrap, projects/omo/src |
| **SOP/Utils** | `sop_*`, `validate_*`, `ci_local.sh`, `release.sh`, `health_scan.*`, `install-cron.sh`, etc. | 18 | L1 | CI, PR template, .omo/standards | lib/paths |
| **Archive** | `archive/` | 23 | — | 无 (历史归档) | — |

---

## 5. 模块图

### L0 共享基础设施 (lib/)

```
lib/
├── __init__.py          包入口
├── bootstrap.py          workspace_root() · omo_src_path() · scripts_dir()
├── paths.py              OMO_DIR · SYSTEM_YAML · TRUTH_DIR · BOS_SERVICES_YAML (30+ 常量)
├── yaml_utils.py         load_yaml() · load_yaml_multi() · write_yaml_atomic() · load_yaml_or_default()
├── cli.py                BaseParser (自动注入 --omo-dir)
├── validators.py         LintReport · require_text() · require_fields() · require_list_min() · match_pattern_list()
├── ssot_checker.py       SSOTChecker · require_text() · forbid_text() · check_targets() · check_targets_with_forbidden()
├── cost_tracker.py       CostTracker · log_call() · summary_by_org() (SQLite, context manager)
└── shell/
    └── common.sh         REPO_ROOT · OMO_DIR · pass() · warn() · fail() · section() · exit_summary()
```

### 功能域 → 入口 → 依赖 映射

```
                    ┌─ .github/workflows/ ────────┐
                    │  governance-check.yml        │
                    │  interfaces-enforce.yml      │
                    │  cross-deps-enforce.yml     │
                    │  port-registry-enforce.yml   │
                    │  state-goals-enforce.yml     │
                    │  meta-model-check.yml        │
                    │  mof-update.yml              │
                    └──────────┬──────────────────┘
                               │ calls
                    ┌──────────▼──────────────────┐
                    │  CI Gates (25 check-*.py)    │
                    │  L1: lib/paths + yaml_utils │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
     Makefile ──────▶  X-Axis Audit (5 x[1-4]-*.sh) │
     governance-     │  L1: lib/shell/common.sh    │
     check target    └──────────┬──────────────────┘
                               │
     Makefile ──────┐ ┌────────▼───────────────────┐
     debt-check     ├▶│  Governance Tools (5)       │
     debt-leaderboard│ │  debt-audit.sh · gov-*     │
                    │ │  L1: lib/shell + lib/paths  │
                    │ └──────────┬──────────────────┘
                    │            │
     cron ──────────┐ │ ┌────────▼───────────────────┐
     (docs cron     ├─┤ │  OPC Automation (17)        │
      schedule)     │ │ │  opc_p5/p6/p7_*              │
                    │ │ │  L2: lib/bootstrap + omo src│
     Makefile ──────┘ │ └──────────┬──────────────────┘
     governance-sync  │            │
                    │ ┌──────────▼──────────────────┐
                    │ │  OMO State Sync (4)          │
                    │ │  sync_omo_state · omo_worker │
                    │ │  L2: lib/bootstrap + omo src │
                    │ └──────────┬──────────────────┘
                    │            │
                    │     ┌──────▼──────┐
                    │     │ projects/   │
                    │     │ omo/src     │
                    │     │ (omo.* 模块) │
                    │     └─────────────┘
                    │
                    │ ┌────────────────────────────┐
     PR template ───┼▶│  SOP/Utils (5)              │
     .omo/standards─┘ │  ci_local.sh · sop_* · ...   │
                      │  L1: lib/paths              │
                      └────────────────────────────┘

     (无引用)
                      ┌────────────────────────────┐
                      │  Archive (23)              │
                      │  archive/                  │
                      │  历史/演示/废弃脚本        │
                      │  归档保留, 不维护          │
                      └────────────────────────────┘
```

---

## 6. 入口模式

脚本被调用的 4 种入口模式：

| 入口 | 模式 | 示例 | 要求 |
|------|------|------|------|
| **CI Gate** | `python3 scripts/check-*.py` | governance-check.yml 调 18 个 check | exit 0=pass, 1=fail |
| **Makefile** | `bash scripts/x1-x4-check.sh` | `make governance-check` | exit 0=pass |
| **Cron** | `python3 scripts/opc_p5_radar_cron.py` | launchd/cron 定时 | 幂等, 写 .omo/_delivery/ |
| **Manual** | `python3 scripts/governance-query.py all` | 人工或 agent 调用 | 可读输出 |

### 入口约定

| 约定 | 说明 |
|------|------|
| CI Gate | 必须无副作用 (只读), exit code 决定 CI pass/fail |
| Makefile | 可有副作用 (生成报告), 但必须幂等 |
| Cron | 必须写 evidence 到 `.omo/_delivery/`, 必须幂等 |
| Manual | 输出人类可读, 支持 `--help` |

---

## 7. 依赖矩阵

| 域 → 依赖 | lib/bootstrap | lib/paths | lib/yaml_utils | lib/shell/common.sh | projects/omo/src |
|-----------|:---:|:---:|:---:|:---:|:---:|
| CI Gates | — | ✅ | ✅ | — | — |
| OPC Auto | ✅ | — | — | — | ✅ |
| X-Axis | — | — | — | ✅ | — |
| Gov Tools | — | ✅ | — | ✅ | — |
| OMO Sync | ✅ | — | — | — | ✅ |
| SOP/Utils | — | ✅ | — | — | — |
| Archive | — | — | — | — | — |

图例: ✅ = 应该依赖, — = 不应依赖

---

## 8. 编码规范

### Python 脚本

```python
#!/usr/bin/env python3
"""一句话描述脚本用途。

用法:
    python3 scripts/foo.py [--omo-dir PATH]
"""
from __future__ import annotations

import sys
from pathlib import Path

# L1 脚本: 只需 lib/paths (自动引入 lib/bootstrap)
from lib.paths import OMO_DIR, SYSTEM_YAML
from lib.yaml_utils import load_yaml

# L2 脚本: 额外需要 omo src
from lib.bootstrap import omo_src_path
sys.path.insert(0, str(omo_src_path()))
from omo.omo_io import write_yaml_atomic


def main() -> int:
    system = load_yaml(SYSTEM_YAML)
    ...


if __name__ == "__main__":
    raise SystemExit(main())
```

### Shell 脚本

```bash
#!/usr/bin/env bash
# foo.sh — 一句话描述

source "$(dirname "$0")/lib/shell/common.sh"

section "My Check"
if [ -f "$OMO_DIR/state/system.yaml" ]; then
    pass "system.yaml exists"
else
    fail "system.yaml missing"
fi

exit_summary
```

### 命名规范

| 前缀 | 含义 | 层 |
|------|------|----|
| `check-*.py` | CI 治理检查 (只读, exit code) | L1 |
| `opc_*` | OPC 自动化 (cron 调度) | L2 |
| `x[1-4]-*.sh` | X 轴审计检查 | L1 |
| `debt-*.sh` | 债务审计工具 | L1 |
| `sync_*.py` | 状态同步脚本 | L2 |
| `verify_*.py` | 阶段验证脚本 (已归档至 archive/) | — |
| `scenario_*.py` | 场景演示脚本 (已归档至 archive/) | — |
| `p[0-9]*` | Phase 一次性脚本 (已归档至 archive/) | — |

---

## 9. 子目录定位

| 目录 | 定位 | 与顶层的关系 |
|------|------|-------------|
| `lib/` | L0 共享基础设施 | 所有脚本的依赖根 |
| `omo/` | OMO 治理高级脚本 | governance-agent.sh (cron), omo_worker.py (78KB 核心), x1/x2/x3 审计 |
| `shell/` | Shell 运维工具 | backup, restore, bridge install, watchdog — 独立运维, 不走 CI |
| `install/` | 安装向导 | setup.sh — 一次性环境配置 |
| `archive/` | 历史归档 | 存放不再维护的历史/演示/废弃脚本 |

`omo/` 子目录脚本使用 `parents[2]` 推导 workspace root (比顶层多一层)。迁移到 `lib/` 后，`lib/bootstrap.workspace_root()` 自动处理深度差异。

---

## 10. 迁移进度

| 阶段 | 内容 | 状态 | 净效果 |
|------|------|------|--------|
| Step 1 | 创建 lib/ 共享层 (5 模块) | ✅ 完成 | 新基础设施 |
| Step 2 | 迁移 7 个 shell + 11 个 Python 脚本 | ✅ 完成 | -77 行重复, 消除 Path.home() x2, sys.path.insert x6 |
| Step 3 | 迁移 26 个 check-*.py + 3 个 omo/ 子目录脚本 | ✅ 完成 | 消除 .omo 路径硬编码 |
| Step 4 | 迁移剩余 41 个脚本 (OPC/shell/historical) | ✅ 完成 | 84/95 脚本迁移 (88%) |
| Step 5 | 提取 validators/ssot_checker/cost_tracker | ✅ 完成 | 3 个可复用 lib/ 模块 |
| Step 6 | 消除所有裸 yaml.safe_load (11 处) | ✅ 完成 | 全部走 lib/yaml_utils |
| Step 7 | 清理 dead imports (3 处) | ✅ 完成 | lint-opc-carriers, check-state-goals, cost_track_org |
| Step 8 | 100% 迁移 + setup_omo_src + ci_local lint | ✅ 完成 | 95/95 (100%), 12 处 sys.path.insert → 0 |
| Step 9 | lib/ 单元测试 | ✅ 完成 | 7 模块 105 tests, 0.10s |
| Step 10 | 归档历史/演示/废弃脚本 | ✅ 完成 | 23 个脚本移至 archive/，顶层剩 72 个活跃脚本 |
| Step 11 | omo_worker.py 拆分 | 不做 | omo 项目自渐进拆分, 等 thin wrapper 化 |

### 量化指标

| 指标 | 原始 | 当前 | 目标 |
|------|------|------|------|
| workspace root 发现模式 | 3 种 | 1 种 (`lib/bootstrap`) | ✅ 1 种 |
| `Path.home()/"Workspace"` | 2 处 | 0 | ✅ 0 |
| `sys.path.insert` 重复 | 15 处 | 9 处 (6 已迁移) | L2 脚本固有需求 |
| shell 颜色 helper 重复 | 7 处 | 0 (全 source common.sh) | ✅ 0 |
| 裸 `yaml.safe_load` | 12 处 | 0 (全走 lib/yaml_utils) | ✅ 0 |
| 裸 `import yaml` (无 lib) | 12 处 | 0 | ✅ 0 |
| lib/ 依赖脚本数 | 0 | 72 (100% 活跃脚本) | ✅ 100% |
| 活跃顶层脚本数 | 95 | 72 | ✅ 72 |
| 归档脚本数 | 0 | 23 | ✅ 23 |
| lib/ 单元测试 | 0 | 105 (7 模块) | ✅ 105 tests |

---

## 11. 测试

### lib/ 单元测试

`tests/lib/` 覆盖 lib/ 全部 7 个 Python 模块 (shell/common.sh 用 bash -n + 功能测试覆盖):

```bash
# 运行全部 lib/ 测试
python3 -m pytest tests/lib/ -v

# 运行单个模块
python3 -m pytest tests/lib/test_validators.py -v
```

| 测试文件 | 测试数 | 覆盖模块 |
|---------|--------|---------|
| `test_bootstrap.py` | 8 | workspace_root, omo_src_path, setup_omo_src |
| `test_paths.py` | 11 | 路径常量存在性 + 层级关系 |
| `test_yaml_utils.py` | 18 | load_yaml, load_yaml_multi, write_yaml_atomic, load_yaml_or_default |
| `test_validators.py` | 21 | LintReport, require_*, match_pattern_list |
| `test_ssot_checker.py` | 20 | SSOTChecker require/forbid/check_targets |
| `test_cost_tracker.py` | 14 | CostTracker log_call, summary_by_org, schema, context manager |
| `test_cli.py` | 6 | BaseParser 默认/自定义参数 |

### CI 集成

`ci_local.sh` step 0 自动检查新脚本是否使用 lib/:
```bash
bash ci_local.sh  # 跑 step 0 (lib/ 检查) + step 1-9 (kairon/omo CI)
```

---

## 12. 约束与风险

| 约束 | 说明 |
|------|------|
| **CI 路径不可变** | `.github/workflows/*.yml` 硬编码 `scripts/check-*.py`，移动文件 break CI |
| **子模块指针** | 改动需先 commit 子模块，再 bump 根仓库指针 |
| **跨子模块耦合** | 15 个脚本依赖 `projects/omo/src` 内部模块，omo API 变动会 break 脚本 |
| **omo_worker.py** | 1822 行, 78KB, import 20+ omo 模块。是稳定核心，拆分风险高 |

### 风险缓解

| 风险 | 缓解 |
|------|------|
| omo API 变动 break 脚本 | `lib/bootstrap.omo_src_path()` 统一注入点, 便于未来改 import 策略 |
| 新脚本不走 lib/ | CI lint 检查: `rg "Path\(__file__\).*parents\[" scripts/*.py` 新增即告警 |
| 历史脚本堆积 | 已迁移至 archive/ 子目录，顶层保持整洁；INDEX.md 标注归档清单 |
