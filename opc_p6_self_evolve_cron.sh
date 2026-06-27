#!/usr/bin/env bash
# OPC P6 self-evolve cron wrapper.
#
# 触发源语义:
#   - cron 调用 (crontab 行带 INVOCATION_ID=cron + OPC_TRIGGER=cron) → 透传
#   - manual 调用                                                  → 强制 OPC_TRIGGER=manual
set -euo pipefail

source "$(dirname "$0")/lib/shell/common.sh"

cd "$REPO_ROOT"

if [ -z "${OPC_TRIGGER:-}" ]; then
    if [ "${INVOCATION_ID:-}" = "cron" ]; then
        export OPC_TRIGGER="cron"
    else
        export OPC_TRIGGER="manual"
    fi
fi

exec python3 scripts/opc_p6_self_evolve.py
