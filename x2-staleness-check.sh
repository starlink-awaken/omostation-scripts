#!/usr/bin/env bash
# x2-staleness-check.sh — X2 抗熵检查
#
# 检查数据是否新鲜：债务新鲜度 + 健康度趋势

source "$(dirname "$0")/lib/shell/common.sh"

SYSTEM_YAML="$OMO_DIR/state/system.yaml"

echo -e "${CYAN}═══ X2 抗熵检查 ═══${NC}"
echo ""

# 1. 债务权重检查
echo "1. 债务权重 (debt_weight)"
if [ -f "$SYSTEM_YAML" ]; then
    DEBT_WEIGHT=$(grep "debt_weight:" "$SYSTEM_YAML" | head -1 | awk '{print $2}')
    if [ "$(echo "$DEBT_WEIGHT >= 0.9" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
        pass "debt_weight = $DEBT_WEIGHT (≥ 0.9)"
    elif [ "$(echo "$DEBT_WEIGHT >= 0.7" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
        warn "debt_weight = $DEBT_WEIGHT (0.7-0.9)"
    else
        fail "debt_weight = $DEBT_WEIGHT (< 0.7)"
    fi
else
    fail "system.yaml 不存在"
fi

# 2. 债务健康度检查
echo "2. 债务健康度 (debt_health)"
if [ -f "$SYSTEM_YAML" ]; then
    DEBT_HEALTH=$(grep "debt_health:" "$SYSTEM_YAML" | head -1 | awk '{print $2}')
    if [ "$(echo "$DEBT_HEALTH >= 90" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
        pass "debt_health = $DEBT_HEALTH (≥ 90)"
    elif [ "$(echo "$DEBT_HEALTH >= 70" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
        warn "debt_health = $DEBT_HEALTH (70-90)"
    else
        fail "debt_health = $DEBT_HEALTH (< 70)"
    fi
fi

# 3. 健康度趋势检查
echo "3. 健康度趋势"
TREND_FILE="$OMO_DIR/_control/debt-dashboard/health-trend.md"
if [ -f "$TREND_FILE" ]; then
    pass "health-trend.md 存在"
    # 检查趋势是否向上
    LAST_WEIGHT=$(grep -E "^\|.*\|[0-9]" "$TREND_FILE" | tail -1 | awk -F'|' '{print $3}' | tr -d ' ')
    if [ -n "$LAST_WEIGHT" ]; then
        pass "最新 debt_weight = $LAST_WEIGHT"
    fi
else
    warn "health-trend.md 不存在"
fi

# 4. 债务解决率检查
echo "4. 债务解决率"
if [ -f "$SYSTEM_YAML" ]; then
    RESOLVED=$(grep "resolved_count:" "$SYSTEM_YAML" | head -1 | awk '{print $2}')
    UNRESOLVED=$(grep "unresolved_count:" "$SYSTEM_YAML" | head -1 | awk '{print $2}')
    TOTAL=$((RESOLVED + UNRESOLVED))
    if [ "$TOTAL" -gt 0 ]; then
        RATE=$((RESOLVED * 100 / TOTAL))
        if [ "$RATE" -ge 90 ]; then
            pass "解决率 = $RATE% (≥ 90%)"
        elif [ "$RATE" -ge 70 ]; then
            warn "解决率 = $RATE% (70-90%)"
        else
            fail "解决率 = $RATE% (< 70%)"
        fi
    fi
fi

echo ""
echo -e "${CYAN}═══ X2 结果: $ERRORS 错误, $WARNINGS 警告 ═══${NC}"

[ $ERRORS -gt 0 ] && exit 1 || exit 0
