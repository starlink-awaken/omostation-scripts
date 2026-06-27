#!/usr/bin/env bash
# x1-audit-check.sh — X1 审计链检查
#
# 检查操作是否安全：债务审计 + 操作审计

source "$(dirname "$0")/lib/shell/common.sh"

echo -e "${CYAN}═══ X1 审计链检查 ═══${NC}"
echo ""

# 1. 债务审计检查
echo "1. 债务审计"
if [ -f "$REPO_ROOT/scripts/debt-audit.sh" ]; then
    pass "debt-audit.sh 存在"
else
    fail "debt-audit.sh 不存在"
fi

# 2. 审计报告检查
echo "2. 审计报告"
if [ -f "$REPO_ROOT/debt-audit-report.md" ]; then
    # 检查报告是否过期 (7天)
    MOD_DAYS=$(( ($(date +%s) - $(stat -f %m "$REPO_ROOT/debt-audit-report.md" 2>/dev/null || echo 0)) / 86400 ))
    if [ "$MOD_DAYS" -le 7 ]; then
        pass "审计报告最近更新 ($MOD_DAYS 天前)"
    else
        warn "审计报告已 $MOD_DAYS 天未更新"
    fi
else
    warn "审计报告不存在"
fi

# 3. pre-commit hook 检查
echo "3. Pre-commit 审计钩子"
for proj in projects/kairon projects/agora projects/cockpit projects/ecos projects/omo projects/metaos projects/runtime; do
    if [ -f "$REPO_ROOT/$proj/.githooks/pre-commit" ]; then
        if grep -q "atomic_write\|debt" "$REPO_ROOT/$proj/.githooks/pre-commit" 2>/dev/null; then
            pass "$(basename $proj): 审计钩子已配置"
        else
            warn "$(basename $proj): 审计钩子缺少债务检查"
        fi
    else
        warn "$(basename $proj): 缺少 .githooks/pre-commit"
    fi
done

echo ""
echo -e "${CYAN}═══ X1 结果: $ERRORS 错误, $WARNINGS 警告 ═══${NC}"

[ $ERRORS -gt 0 ] && exit 1 || exit 0
