#!/usr/bin/env bash
# install-cron.sh — 安装治理检查 Cron 任务
#
# 用法: bash scripts/install-cron.sh

source "$(dirname "$0")/lib/shell/common.sh"

CRON_FILE="$REPO_ROOT/.omo/cron/governance-crontab"

echo "=== 安装治理检查 Cron ==="
echo ""

# 检查 cron 文件
if [ ! -f "$CRON_FILE" ]; then
    echo "❌ Cron 文件不存在: $CRON_FILE"
    exit 1
fi

# 备份现有 crontab
EXISTING=$(crontab -l 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
    echo "📋 备份现有 crontab 到 ~/.crontab.backup"
    echo "$EXISTING" > ~/.crontab.backup
fi

# 合并 crontab
echo "📝 合并治理 cron 任务..."
(crontab -l 2>/dev/null | grep -v "governance\|debt-audit"; cat "$CRON_FILE") | crontab -

echo "✅ Cron 安装完成"
echo ""
echo "当前 crontab:"
crontab -l | grep -E "governance|debt-audit" || echo "  (无治理相关任务)"
