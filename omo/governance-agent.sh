#!/bin/bash
# P61 自治治理代理 — 每 6h 跑一次 governance-readiness
#
# 功能:
# 1. 跑 bin/governance-readiness.py 评估 5 维度
# 2. 跑 bin/mof-drift 跨 7 维度 (含 P61 commit_closure + governance_score_history)
# 3. 写结果到 .omo/_log/governance-agent-YYYYMMDD-HHMM.log
# 4. 若总分 < 90 或 drift MEDIUM/HIGH, 通过 emit signal 告警 (P61 扩展)
#
# 触发: cron 每 6h (详见 .omo/cron/governance-agent-crontab)

set -e

# 解析脚本位置, 找到 workspace 根
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
LOG_DIR="$WORKSPACE_ROOT/.omo/_log"
TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
LOG_FILE="$LOG_DIR/governance-agent-$TIMESTAMP.log"

mkdir -p "$LOG_DIR"

cd "$WORKSPACE_ROOT" || { echo "FATAL: cd $WORKSPACE_ROOT failed" | tee -a "$LOG_FILE"; exit 2; }

echo "=== P61 自治治理代理 @ $TIMESTAMP ===" | tee -a "$LOG_FILE"

# 1. governance-readiness
echo "" | tee -a "$LOG_FILE"
echo "--- [1/3] governance-readiness ---" | tee -a "$LOG_FILE"
python3 bin/governance-readiness.py 2>&1 | tee -a "$LOG_FILE"
READINESS_EXIT=$?

# 2. mof-drift
echo "" | tee -a "$LOG_FILE"
echo "--- [2/3] mof-drift ---" | tee -a "$LOG_FILE"
bin/mof-drift 2>&1 | tee -a "$LOG_FILE"
DRIFT_EXIT=$?

# 3. 健康度评估
echo "" | tee -a "$LOG_FILE"
echo "--- [3/3] 评估 ---" | tee -a "$LOG_FILE"

TOTAL_LOW=0
TOTAL_MEDIUM=0
TOTAL_HIGH=0

# 解析 readiness 评分
READINESS_SCORE=$(grep -E "^总分" "$LOG_FILE" | head -1 | grep -oE "[0-9]+" | head -1)
if [ -z "$READINESS_SCORE" ]; then
    READINESS_SCORE=0
fi

# 解析 drift 严重度 (用 2>/dev/null 抑制子 shell 错误)
DRIFT_OUTPUT=$(bin/mof-drift 2>/dev/null)
TOTAL_LOW=$(echo "$DRIFT_OUTPUT" | grep -c "🔵 LOW" 2>/dev/null | head -1 || echo "0")
TOTAL_MEDIUM=$(echo "$DRIFT_OUTPUT" | grep -c "🟡 MEDIUM" 2>/dev/null | head -1 || echo "0")
TOTAL_HIGH=$(echo "$DRIFT_OUTPUT" | grep -c "🔴 HIGH" 2>/dev/null | head -1 || echo "0")
TOTAL_LOW=$(echo "$TOTAL_LOW" | head -1)
TOTAL_MEDIUM=$(echo "$TOTAL_MEDIUM" | head -1)
TOTAL_HIGH=$(echo "$TOTAL_HIGH" | head -1)

echo "readiness: $READINESS_SCORE/100" | tee -a "$LOG_FILE"
echo "drift: LOW=$TOTAL_LOW MEDIUM=$TOTAL_MEDIUM HIGH=$TOTAL_HIGH" | tee -a "$LOG_FILE"

# 4. 信号告警 (P61 扩展: 通过 omo event 发射)
ALERT=false
if [ "$READINESS_SCORE" -lt 90 ]; then
    echo "⚠️  readiness < 90, 触发告警" | tee -a "$LOG_FILE"
    ALERT=true
fi
if [ "$TOTAL_MEDIUM" -gt 0 ] || [ "$TOTAL_HIGH" -gt 0 ]; then
    echo "⚠️  drift MEDIUM/HIGH 出现, 触发告警" | tee -a "$LOG_FILE"
    ALERT=true
fi

if [ "$ALERT" = true ]; then
    # P61 扩展: omo event emit (后续 P62 实施完整事件总线)
    if command -v omo >/dev/null 2>&1; then
        omo event emit \
            --type governance_alert \
            --source governance-agent \
            --payload "{\"readiness\":$READINESS_SCORE,\"drift_low\":$TOTAL_LOW,\"drift_medium\":$TOTAL_MEDIUM,\"drift_high\":$TOTAL_HIGH,\"timestamp\":\"$TIMESTAMP\"}" \
            2>&1 | tee -a "$LOG_FILE" || echo "(omo event 不可用, 跳过)" | tee -a "$LOG_FILE"
    fi
    exit 1
fi

echo "" | tee -a "$LOG_FILE"
echo "✅ 自治治理代理正常, 退出码 0" | tee -a "$LOG_FILE"
exit 0