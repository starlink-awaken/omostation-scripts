# omostation-scripts

> Omostation 工作站的运维脚本和自动化工具集合。

## 目录结构

```
scripts/
├── omo/       ── OMO 治理脚本
├── shell/     ── Shell 工具脚本
└── install/   ── 安装与配置向导
```

## 用法

作为子模块挂载在 `~/Workspace/scripts/` 下：

```bash
cd ~/Workspace
git submodule update --init scripts/
```

脚本通过 `~/.hermes/scripts/` 桥接至 Hermes Agent，通过软链接在 Workspace 中可用。

## 治理

- Shell 脚本需通过 shellcheck 检查
- 新增脚本需在顶层目录添加软链接入口
- 不包含运行时凭证或环境依赖

## 层位置

跨层运维工具，不归属于任一 eCOS 层。通过 Hermes cron 和 cron-service 调度。
