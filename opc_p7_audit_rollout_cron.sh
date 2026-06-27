#!/usr/bin/env bash
# OPC P7 audit rollout cron wrapper.
#
# 模式 (env OPC_MODE):
#   weekly        — 默认, 每周一次
#   monthly       — 每月一次
#   pre-release   — 发布前 (CI 触发)
#
# 触发源语义 (同 P7 release / P6 self-evolve):
#   - cron 调用 (crontab 行带 INVOCATION_ID=cron + OPC_TRIGGER=cron) → 透传
#   - manual 调用                                                  → 强制 OPC_TRIGGER=manual
#
# crontab 示例 (Mon 02:00 weekly + 1st 03:00 monthly):
#   0 2 * * 1 INVOCATION_ID=cron OPC_TRIGGER=cron OPC_MODE=weekly /Users/xiamingxing/Workspace/scripts/opc_p7_audit_rollout_cron.sh
#   0 3 1 * * INVOCATION_ID=cron OPC_TRIGGER=cron OPC_MODE=monthly /Users/xiamingxing/Workspace/scripts/opc_p7_audit_rollout_cron.sh
set -euo pipefail

source "$(dirname "$0")/lib/shell/common.sh"

OPC_MODE="${OPC_MODE:-weekly}"

cd "$REPO_ROOT"

if [ -z "${OPC_TRIGGER:-}" ]; then
    if [ "${INVOCATION_ID:-}" = "cron" ]; then
        export OPC_TRIGGER="cron"
    else
        export OPC_TRIGGER="manual"
    fi
fi

# daemon 永远以 wrapper 退出码为准, 即便 rollout 失败
python3 scripts/opc_p7_audit_rollout_daemon.py
