#!/usr/bin/env bash
# x4-consistency-check.sh — X4 一致性检查
#
# 检查规则是否被遵守：CI + pre-commit + 文档

source "$(dirname "$0")/lib/shell/common.sh"

echo -e "${CYAN}═══ X4 一致性检查 ═══${NC}"
echo ""

# 1. CI 工作流检查
echo "1. CI 工作流"
CI_DIR="$REPO_ROOT/.github/workflows"
if [ -d "$CI_DIR" ]; then
    CI_COUNT=$(ls "$CI_DIR"/*.yml 2>/dev/null | wc -l | tr -d ' ')
    if [ "$CI_COUNT" -ge 10 ]; then
        pass "CI 工作流: $CI_COUNT 个 (≥ 10)"
    elif [ "$CI_COUNT" -ge 5 ]; then
        warn "CI 工作流: $CI_COUNT 个 (5-10)"
    else
        fail "CI 工作流: $CI_COUNT 个 (< 5)"
    fi
    
    # 检查债务审计 CI
    if [ -f "$CI_DIR/debt-audit.yml" ]; then
        pass "debt-audit.yml 存在"
    else
        warn "debt-audit.yml 不存在"
    fi
else
    fail ".github/workflows/ 不存在"
fi

# 2. pre-commit 配置检查
echo "2. Pre-commit 配置"
for proj in projects/kairon projects/agora projects/cockpit projects/ecos projects/omo projects/metaos projects/runtime; do
    if [ -d "$REPO_ROOT/$proj/.githooks" ]; then
        pass "$(basename $proj): .githooks/ 存在"
    else
        fail "$(basename $proj): .githooks/ 不存在"
    fi
done

# 3. 文档一致性检查
echo "3. 文档一致性"
DOCS=("AGENTS.md" "CLAUDE.md")
for doc in "${DOCS[@]}"; do
    if [ -f "$REPO_ROOT/$doc" ]; then
        # 检查是否有版本信息
        if grep -Eq "最后更新|last_updated|version" "$REPO_ROOT/$doc" 2>/dev/null; then
            pass "$doc: 有版本信息"
        else
            warn "$doc: 缺少版本信息"
        fi
    else
        warn "$doc: 不存在"
    fi
done

# 4. 治理数据一致性
echo "4. 治理数据一致性"
if [ -f "$REPO_ROOT/.omo/_control/governance-data.json" ]; then
    pass "governance-data.json 存在"
    # 检查数据是否过期
    MOD_DAYS=$(( ($(date +%s) - $(stat -f %m "$REPO_ROOT/.omo/_control/governance-data.json" 2>/dev/null || echo 0)) / 86400 ))
    if [ "$MOD_DAYS" -le 1 ]; then
        pass "治理数据最近更新"
    else
        warn "治理数据已 $MOD_DAYS 天未更新"
    fi
else
    warn "governance-data.json 不存在"
fi

echo ""
echo -e "${CYAN}═══ X4 结果: $ERRORS 错误, $WARNINGS 警告 ═══${NC}"

[ $ERRORS -gt 0 ] && exit 1 || exit 0
