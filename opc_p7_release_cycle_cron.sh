#!/usr/bin/env bash
# OPC P7 release cycle cron wrapper.
#
# 设计:
#   - cron 入口 (e.g. crontab): 自动注入 OPC_TRIGGER=cron
#   - manual 入口: 不注入, 留 trigger 透传 (默认 manual)
#
# 区分方法: 调用方是否在 cron 调度下 (由 .omo/cron/ 下的 crontab 文件管理).
#   - crontab 行:    0 23 * * 0 ... bash opc_p7_release_cycle_cron.sh
#                   → wrapper 内部检测 "caller is cron", 注入 OPC_TRIGGER=cron
#   - 手动运行:     bash opc_p7_release_cycle_cron.sh
#                   → wrapper 内部检测 "caller is tty/interactive", 不注入
#
# 显式 override: 调用方设 OPC_TRIGGER=cron 仍透传, 不被覆盖.
set -euo pipefail

WORKSPACE="${WORKSPACE:-/Users/xiamingxing/Workspace}"
OPC_RELEASE_CUTOFF="${OPC_RELEASE_CUTOFF:-7 days ago}"

cd "$WORKSPACE"

# 触发源判定:
#   1. 若调用方已显式设置 OPC_TRIGGER, 透传 (优先级最高)
#   2. 否则, 若 INVOCATION_ID == "cron" (cron 调度), 注入 cron
#   3. 否则 (manual / interactive), 留空 (Python 端默认 manual)
if [ -z "${OPC_TRIGGER:-}" ]; then
    if [ "${INVOCATION_ID:-}" = "cron" ]; then
        export OPC_TRIGGER="cron"
    else
        # manual 显式标 manual, 防止 Python 端 fallback 误判
        export OPC_TRIGGER="manual"
    fi
fi

exec python3 scripts/opc_p7_release_cycle.py
