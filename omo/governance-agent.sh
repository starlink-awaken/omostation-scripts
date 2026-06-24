#!/bin/bash
# P61 自治治理代理 — 每 6h 跑一次 governance-readiness
#
# 用法:
#   governance-agent.sh                       # 标准运行
#   governance-agent.sh --dry-run             # dry-run 模式 (不写日志, 不告警)
#   governance-agent.sh --snapshot-only       # 只跑 readiness + 写快照
#   governance-agent.sh --include-trend       # 跑 readiness + drift + trend
#
# 功能:
# 1. 跑 bin/governance-readiness.py 评估 5 维度
# 2. 跑 bin/mof-drift 跨 8 维度 (含 P61 commit_closure + P62 stale_governance)
# 3. (--include-trend) 跑 bin/governance-readiness-trend.py 趋势分析
# 4. 写结果到 .omo/_log/governance-agent-YYYYMMDD-HHMM.log
# 5. readiness 快照自动写入 .omo/_log/readiness-YYYYMMDD-HHMM.json (P63)
# 6. 若总分 < 90 或 drift MEDIUM/HIGH, 通过 emit signal 告警
#
# 触发: cron 每 6h (详见 .omo/cron/governance-agent-crontab)

set -e

# 解析参数
DRY_RUN=false
SNAPSHOT_ONLY=false
INCLUDE_TREND=false
for arg in "$@"; do
    case "$arg" in
        --dry-run)         DRY_RUN=true ;;
        --snapshot-only)   SNAPSHOT_ONLY=true ;;
        --include-trend)   INCLUDE_TREND=true ;;
        --help|-h)
            echo "用法: governance-agent.sh [--dry-run] [--snapshot-only] [--include-trend]"
            exit 0
            ;;
    esac
done

# 解析脚本位置, 找到 workspace 根
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
LOG_DIR="$WORKSPACE_ROOT/.omo/_log"
TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
LOG_FILE="$LOG_DIR/governance-agent-$TIMESTAMP.log"

if [ "$DRY_RUN" = false ]; then
    mkdir -p "$LOG_DIR"
fi

cd "$WORKSPACE_ROOT" || { echo "FATAL: cd $WORKSPACE_ROOT failed"; exit 2; }

# P72: emit mutation intent before any .omo/ writes
RUN_ID=$(python3 -c "import uuid; print(uuid.uuid4().hex[:8])")
if command -v omo >/dev/null 2>&1; then
    omo event emit \
        --type agent_mutation_intent \
        --source governance-agent \
        --payload "{\"run_id\":\"$RUN_ID\",\"trigger\":\"cron\",\"planned_surfaces\":[\".omo/_log\",\".omo/_control/evolution/drift\",\".omo/_knowledge\"]}" \
        2>/dev/null || true
fi

# dry-run 跳过 tee 到日志
if [ "$DRY_RUN" = true ]; then
    exec > >(cat) 2>&1
    echo "=== P63 自治治理代理 (DRY-RUN) @ $TIMESTAMP ==="
else
    echo "=== P61 自治治理代理 @ $TIMESTAMP ===" | tee -a "$LOG_FILE"
fi

# 1. governance-readiness
echo ""
echo "--- [1/3] governance-readiness ---"
if [ "$DRY_RUN" = false ]; then
    python3 bin/governance-readiness.py 2>&1 | tee -a "$LOG_FILE"
    # 解析总分: 从日志读
    READINESS_SCORE_LOCAL=$(grep -E "^总分" "$LOG_FILE" | head -1 | grep -oE "[0-9]+" | head -1)
else
    # dry-run: 直接 capture stdout
    READINESS_OUTPUT=$(python3 bin/governance-readiness.py 2>&1)
    echo "$READINESS_OUTPUT"
    READINESS_SCORE_LOCAL=$(echo "$READINESS_OUTPUT" | grep -E "^总分" | head -1 | grep -oE "[0-9]+" | head -1)
fi
READINESS_EXIT=$?
[ -z "$READINESS_SCORE_LOCAL" ] && READINESS_SCORE_LOCAL=0

# snapshot-only 模式: 跑完 readiness 直接退出
if [ "$SNAPSHOT_ONLY" = true ]; then
    echo "--- snapshot-only: 已完成 readiness 评估 + 快照 ---"
    exit 0
fi

# 2. mof-drift
echo ""
echo "--- [2/3] mof-drift ---"
if [ "$DRY_RUN" = false ]; then
    bin/mof-drift 2>&1 | tee -a "$LOG_FILE"
    DRIFT_OUTPUT=$(bin/mof-drift 2>/dev/null)
else
    DRIFT_OUTPUT=$(bin/mof-drift 2>/dev/null)
    echo "$DRIFT_OUTPUT" | head -20
fi
DRIFT_EXIT=$?

# 2.5 (--include-trend) readiness 趋势分析
if [ "$INCLUDE_TREND" = true ]; then
    echo ""
    echo "--- [2.5/3] readiness-trend ---"
    if [ "$DRY_RUN" = false ]; then
        python3 bin/governance-readiness-trend.py 2>&1 | tee -a "$LOG_FILE"
    else
        python3 bin/governance-readiness-trend.py
    fi
    # P67 增: alert-aggregator 评估 (--notify 模式)
    if [ -f .omo/_log/readiness-alerts.jsonl ]; then
        echo ""
        echo "--- [2.6/3] alert-aggregator ---"
        if [ "$DRY_RUN" = false ]; then
            python3 bin/alert-aggregator.py 2>&1 | tee -a "$LOG_FILE"
        else
            python3 bin/alert-aggregator.py
        fi
    fi
    # P71 增: alert-history 步骤 (7d 趋势)
    echo ""
    echo "--- [2.7/3] alert-history ---"
    if [ "$DRY_RUN" = false ]; then
        python3 bin/alert-history.py 2>&1 | tee -a "$LOG_FILE"
    else
        python3 bin/alert-history.py
    fi
fi

# 3. 健康度评估
echo ""
echo "--- [3/3] 评估 ---"
if [ "$DRY_RUN" = false ]; then
    echo "" | tee -a "$LOG_FILE"
    echo "--- [3/3] 评估 ---" | tee -a "$LOG_FILE"
fi

TOTAL_LOW=0
TOTAL_MEDIUM=0
TOTAL_HIGH=0

# 使用步骤 1 已解析的 score (dry-run 模式)
READINESS_SCORE=$READINESS_SCORE_LOCAL

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

# P72: 自治运行产生的 drift/audit/log 必须立即 commit, 避免 dirty 竞争
COMMITTED=false
if [ "$DRY_RUN" = false ]; then
    if [ -n "$(git status --porcelain)" ]; then
        echo "--- [P72] auto-committing agent outputs ---" | tee -a "$LOG_FILE"
        # 子模块先提交
        git submodule foreach --quiet 'git add -A 2>/dev/null; git diff --cached --quiet || git commit -m "chore(agent): auto-commit governance-agent outputs" 2>/dev/null' || true
        # 根仓库提交
        git add -A 2>/dev/null
        if ! git diff --cached --quiet; then
            git commit -m "chore(agent): governance-agent auto-commit ($TIMESTAMP)" 2>&1 | tee -a "$LOG_FILE" || true
            COMMITTED=true
        fi
    fi
fi

if command -v omo >/dev/null 2>&1; then
    COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "")
    omo event emit \
        --type agent_mutation_complete \
        --source governance-agent \
        --payload "{\"run_id\":\"$RUN_ID\",\"committed\":$COMMITTED,\"commit_sha\":\"$COMMIT_SHA\"}" \
        2>/dev/null || true
fi

exit 0