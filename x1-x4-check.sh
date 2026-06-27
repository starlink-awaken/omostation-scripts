#!/usr/bin/env bash
# x1-x4-check.sh — X1-X4 全维度检查
#
# 一键运行所有 X 维度检查

source "$(dirname "$0")/lib/shell/common.sh"

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  X1-X4 治理框架全维度检查${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

TOTAL_ERRORS=0

# X1 审计链
echo -e "${CYAN}▶ X1 审计链${NC}"
if bash "$REPO_ROOT/scripts/x1-audit-check.sh"; then
    echo ""
else
    TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
fi

# X2 抗熵
echo -e "${CYAN}▶ X2 抗熵${NC}"
if bash "$REPO_ROOT/scripts/x2-staleness-check.sh"; then
    echo ""
else
    TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
fi

# X3 价值栈
echo -e "${CYAN}▶ X3 价值栈${NC}"
if bash "$REPO_ROOT/scripts/x3-value-check.sh"; then
    echo ""
else
    TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
fi

# X4 一致性
echo -e "${CYAN}▶ X4 一致性${NC}"
if bash "$REPO_ROOT/scripts/x4-consistency-check.sh"; then
    echo ""
else
    TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
fi

# 汇总
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  汇总: $TOTAL_ERRORS 维度未通过${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

if [ $TOTAL_ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ X1-X4 全维度通过${NC}"
    exit 0
else
    echo -e "${RED}❌ $TOTAL_ERRORS 个维度未通过${NC}"
    exit 1
fi
