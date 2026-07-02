#!/usr/bin/env bash
# x3-value-check.sh — X3 价值栈检查
#
# 检查投入是否合理：债务优先级 + SLA 达成

source "$(dirname "$0")/lib/shell/common.sh"

SYSTEM_YAML="$OMO_DIR/state/system.yaml"

echo -e "${CYAN}═══ X3 价值栈检查 ═══${NC}"
echo ""

# 1. 债务优先级分布
echo "1. 债务优先级分布"
DEBT_ITEMS=$( (grep -L "status: closed" "$OMO_DIR/debt/items/"*.yaml 2>/dev/null || true) | wc -l | tr -d ' ')  # 数 open 债务 (closed 已解决不计)
if [ "$DEBT_ITEMS" -eq 0 ]; then
    pass "无未解决债务"
else
    warn "有 $DEBT_ITEMS 项债务"
    # 检查是否有 critical 债务
    CRITICAL=$( (grep -l "severity: critical" "$OMO_DIR/debt/items/"*.yaml 2>/dev/null || true) | wc -l | tr -d ' ')
    if [ "$CRITICAL" -gt 0 ]; then
        fail "有 $CRITICAL 项 critical 债务"
    fi
fi

# 2. SLA 文档检查
echo "2. SLA 标准"
if [ -f "$OMO_DIR/_knowledge/governance/sla.md" ]; then
    pass "sla.md 存在"
else
    warn "sla.md 不存在"
fi

# 3. 治理文档覆盖
echo "3. 治理文档覆盖"
DOCS=("README.md" "debt-prevention.md" "sla.md" "quickstart.md")
for doc in "${DOCS[@]}"; do
    if [ -f "$OMO_DIR/_knowledge/governance/$doc" ]; then
        pass "$doc 存在"
    else
        warn "$doc 不存在"
    fi
done

# 4. 债务分类检查
echo "4. 债务分类"
CATEGORIES=("technical" "governance" "process")
for cat in "${CATEGORIES[@]}"; do
    set +o pipefail
    CAT_COUNT=$(grep -l "source:" "$OMO_DIR/debt/items/"*.yaml 2>/dev/null | xargs grep -l "$cat" 2>/dev/null | wc -l | tr -d ' ')
    set -o pipefail
    if [ "$CAT_COUNT" -eq 0 ]; then
        pass "$cat: 无债务"
    else
        warn "$cat: $CAT_COUNT 项债务"
    fi
done

echo ""
echo -e "${CYAN}═══ X3 结果: $ERRORS 错误, $WARNINGS 警告 ═══${NC}"

[ $ERRORS -gt 0 ] && exit 1 || exit 0
