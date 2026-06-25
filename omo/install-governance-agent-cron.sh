#!/bin/bash
# P62 governance-agent cron 安装/卸载/状态脚本
#
# 用法:
#   ./install-governance-agent-cron.sh           # 安装 (默认)
#   ./install-governance-agent-cron.sh --uninstall
#   ./install-governance-agent-cron.sh --status
#   ./install-governance-agent-cron.sh --test      # P73: 跑 1 次 dry-run 验证

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER="$SCRIPT_DIR/governance-agent.sh"
CRON_LINE="0 */6 * * * $WRAPPER >> ${WORKSPACE_ROOT:-/Users/xiamingxing/Workspace}/.omo/_log/governance-agent-cron.log 2>&1"
CRON_TAG="# P61 governance-agent-cron"

case "${1:-install}" in
    install)
        # 移除旧 cron 行 (避免重复)
        (crontab -l 2>/dev/null | grep -v "$CRON_TAG" || true) > /tmp/cron.tmp
        echo "$CRON_LINE" >> /tmp/cron.tmp
        echo "$CRON_TAG" >> /tmp/cron.tmp
        crontab /tmp/cron.tmp
        rm /tmp/cron.tmp
        echo "✅ governance-agent cron 已安装: 每 6h 跑"
        echo "   cron line: $CRON_LINE"
        ;;
    --uninstall|uninstall)
        (crontab -l 2>/dev/null | grep -v "$CRON_TAG" | grep -v "$WRAPPER" || true) > /tmp/cron.tmp
        crontab /tmp/cron.tmp
        rm /tmp/cron.tmp
        echo "✅ governance-agent cron 已卸载"
        ;;
    --test|test)
        # P73 增: --test 模式跑 1 次 dry-run 验证
        echo "=== governance-agent --test 模式 (dry-run) ==="
        echo "将执行: $WRAPPER --include-trend --dry-run"
        echo ""
        "$WRAPPER" --include-trend --dry-run
        echo ""
        echo "✅ --test 完成 (未修改 crontab, 未写 alert log)"
        ;;
    --status|status)
        echo "=== governance-agent cron 状态 ==="
        if crontab -l 2>/dev/null | grep -q "$WRAPPER"; then
            echo "✅ 已安装"
            crontab -l 2>/dev/null | grep "$WRAPPER" | head -3
        else
            echo "❌ 未安装"
        fi
        echo ""
        echo "=== 最近 5 次运行 ==="
        if [ -d "${WORKSPACE_ROOT:-/Users/xiamingxing/Workspace}/.omo/_log" ]; then
            ls -lt "${WORKSPACE_ROOT:-/Users/xiamingxing/Workspace}/.omo/_log"/governance-agent-*.log 2>/dev/null | head -5
        fi
        ;;
    --status-json|status-json)
        # P76 增: 输出结构化 JSON 状态 (供 dashboard/工具消费)
        if crontab -l 2>/dev/null | grep -q "$WRAPPER"; then
            INSTALLED="true"
            CRON_LINE_OUTPUT=$(crontab -l 2>/dev/null | grep "$WRAPPER" | head -1)
        else
            INSTALLED="false"
            CRON_LINE_OUTPUT=""
        fi
        # 统计最近运行次数
        RUN_COUNT=0
        if [ -d "${WORKSPACE_ROOT:-/Users/xiamingxing/Workspace}/.omo/_log" ]; then
            RUN_COUNT=$(ls "${WORKSPACE_ROOT:-/Users/xiamingxing/Workspace}/.omo/_log"/governance-agent-*.log 2>/dev/null | wc -l | tr -d ' ')
        fi
        # 输出 JSON
        cat <<EOF
{
    "installed": ${INSTALLED},
    "cron_line": "${CRON_LINE_OUTPUT}",
    "wrapper": "${WRAPPER}",
    "workspace_root": "${WORKSPACE_ROOT:-/Users/xiamingxing/Workspace}",
    "log_dir": "${WORKSPACE_ROOT:-/Users/xiamingxing/Workspace}/.omo/_log",
    "run_count": ${RUN_COUNT},
    "command": "governance-agent.sh"
}
EOF
        ;;
    *)
        echo "用法: $0 [install|--uninstall|--status]"
        exit 1
        ;;
esac