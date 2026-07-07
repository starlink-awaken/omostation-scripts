#!/usr/bin/env bash
# debt-audit.sh — 定期债务审计脚本
#
# 用法:
#   bash scripts/debt-audit.sh              # 审计并输出报告
#   bash scripts/debt-audit.sh --notify     # 审计并通知 (需配置)
#   bash scripts/debt-audit.sh --fix        # 审计并尝试自动修复
#
# Cron 配置示例:
#   0 9 * * 1  cd ~/Workspace && bash scripts/debt-audit.sh --notify

source "$(dirname "$0")/lib/shell/common.sh"

SYSTEM_YAML="$OMO_DIR/state/system.yaml"
DASHBOARD_YAML="$OMO_DIR/_control/debt-dashboard/current.yaml"
REPORT_FILE="$REPO_ROOT/debt-audit-report.md"

# ── 1. 债务状态检查 ────────────────────────────────────────────────────────────

check_debt_status() {
    section "债务状态"
    
    if [ ! -f "$SYSTEM_YAML" ]; then
        warn "system.yaml 不存在 (CI 环境可能缺少运行时状态)"
        DEBT_WEIGHT=""
        DEBT_HEALTH=""
        RESOLVED="0"
        UNRESOLVED="0"
        return
    fi
    
    # 提取债务指标 (|| true 防 grep 无匹配时 pipefail 退出)
    DEBT_WEIGHT=$(grep "debt_weight:" "$SYSTEM_YAML" | head -1 | awk '{print $2}' || true)
    DEBT_HEALTH=$(grep "debt_health:" "$SYSTEM_YAML" | head -1 | awk '{print $2}' || true)
    RESOLVED=$(grep "resolved_count:" "$SYSTEM_YAML" | head -1 | awk '{print $2}' || true)
    UNRESOLVED=$(grep "unresolved_count:" "$SYSTEM_YAML" | head -1 | awk '{print $2}' || true)
    
    echo "  debt_weight: $DEBT_WEIGHT"
    echo "  debt_health: $DEBT_HEALTH"
    echo "  resolved: $RESOLVED"
    echo "  unresolved: $UNRESOLVED"
    
    # 检查阈值 (空值时跳过, 兼容 CI)
    if [ -n "$DEBT_WEIGHT" ] && [ "$(echo "$DEBT_WEIGHT < 0.9" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
        warn "debt_weight < 0.9 ($DEBT_WEIGHT)"
    elif [ -n "$DEBT_WEIGHT" ]; then
        pass "debt_weight >= 0.9"
    fi
    
    if [ -n "$DEBT_HEALTH" ] && [ "$(echo "$DEBT_HEALTH < 90" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
        warn "debt_health < 90 ($DEBT_HEALTH)"
    elif [ -n "$DEBT_HEALTH" ]; then
        pass "debt_health >= 90"
    fi
    
    if [ -n "$UNRESOLVED" ] && [ "$UNRESOLVED" -gt 0 ] 2>/dev/null; then
        warn "有 $UNRESOLVED 项未解决债务"
    else
        pass "所有债务已解决"
    fi
}

# ── 2. 新增非原子写入检查 ──────────────────────────────────────────────────────

check_atomic_writes() {
    section "非原子写入检查"
    
    NON_ATOMIC_COUNT=0
    
    # 只检查最近修改的文件（通过 git diff）
    for proj in projects/kairon projects/agora projects/cockpit projects/ecos projects/omo projects/metaos projects/runtime; do
        if [ ! -d "$REPO_ROOT/$proj" ]; then
            continue
        fi
        
        cd "$REPO_ROOT/$proj"
        # 获取最近 7 天修改的 Python 文件
        RECENT_FILES=$(git diff --name-only HEAD~5 2>/dev/null | grep "\.py$" | grep -v test | grep -v __pycache__ | head -10 || true)
        
        for f in $RECENT_FILES; do
            FULL_PATH="$REPO_ROOT/$proj/$f"
            if [ ! -f "$FULL_PATH" ]; then
                continue
            fi
            if grep -qE "write_text|open\([^)]*['\"]w['\"]" "$FULL_PATH" 2>/dev/null; then
                if ! grep -q "atomic_write" "$FULL_PATH" 2>/dev/null; then
                    warn "潜在非原子写入: $proj/$f"
                    NON_ATOMIC_COUNT=$((NON_ATOMIC_COUNT + 1))
                fi
            fi
        done
        cd "$REPO_ROOT"
    done
    
    if [ "$NON_ATOMIC_COUNT" -eq 0 ]; then
        pass "无新增非原子写入"
    fi
}

# ── 3. 测试覆盖检查 ────────────────────────────────────────────────────────────

check_test_coverage() {
    section "测试覆盖检查"
    
    for proj in projects/kairon; do
        if [ ! -d "$REPO_ROOT/$proj/packages" ]; then
            continue
        fi
        
        for pkg in "$REPO_ROOT/$proj/packages"/*/; do
            if [ ! -d "$pkg" ]; then
                continue
            fi
            
            PKG_NAME=$(basename "$pkg")
            
            # 跳过已归档的包
            if echo "$PKG_NAME" | grep -q "archived"; then
                continue
            fi
            
            if [ ! -d "$pkg/tests" ]; then
                warn "kairon/$PKG_NAME 缺少 tests/ 目录"
            fi
        done
    done
    
    pass "测试覆盖检查完成"
}

# ── 4. 文档新鲜度检查 ──────────────────────────────────────────────────────────

check_doc_freshness() {
    section "文档新鲜度检查"
    
    for doc in AGENTS.md CLAUDE.md; do
        if [ -f "$REPO_ROOT/$doc" ]; then
            # 检查最后修改时间 (GNU stat -c %Y 先: Linux CI; BSD stat -f %m 后: macOS 本地)
            # 注意顺序不能反: GNU stat -f 是 --file-system 模式, 输出 "File:" 标题 exit 0 不 fail,
            # 导致 BSD 先时 MOD_TIME 拿到垃圾多行值触发 set -u "File: unbound variable"
            MOD_TIME=$(stat -c %Y "$REPO_ROOT/$doc" 2>/dev/null || stat -f %m "$REPO_ROOT/$doc" 2>/dev/null || echo 0)
            MOD_DAYS=$(( ($(date +%s) - "$MOD_TIME") / 86400 ))
            if [ "$MOD_DAYS" -gt 30 ]; then
                warn "$doc 已 $MOD_DAYS 天未更新"
            else
                pass "$doc 最近更新 ($MOD_DAYS 天前)"
            fi
        fi
    done
}

# ── 5. 生成报告 ────────────────────────────────────────────────────────────────

generate_report() {
    section "生成审计报告"
    
    cat > "$REPORT_FILE" << EOF
# 债务审计报告

> 生成时间: $(date '+%Y-%m-%d %H:%M:%S')
> 仓库: $REPO_ROOT

## 审计结果

- 错误: $ERRORS
- 警告: $WARNINGS

## 债务状态

- debt_weight: $DEBT_WEIGHT
- debt_health: $DEBT_HEALTH
- resolved: $RESOLVED
- unresolved: $UNRESOLVED

## 建议

$([ $ERRORS -gt 0 ] && echo "- 🔴 有 $ERRORS 个错误需要修复" || echo "- ✅ 无错误")
$([ $WARNINGS -gt 0 ] && echo "- ⚠️ 有 $WARNINGS 个警告需要关注" || echo "- ✅ 无警告")

---

*自动生成 by debt-audit.sh*
EOF
    
    pass "报告已生成: $REPORT_FILE"
}

# ── Main ────────────────────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  债务审计 — $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"

check_debt_status
check_atomic_writes
check_test_coverage
check_doc_freshness
generate_report

# ── 结果 ────────────────────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  结果: $ERRORS 错误, $WARNINGS 警告${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}❌ 审计未通过 — 有 $ERRORS 个错误需要修复${NC}"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  审计通过但有警告 — $WARNINGS 个警告需要关注${NC}"
    exit 0
else
    echo -e "${GREEN}✅ 审计通过 — 无错误无警告${NC}"
    exit 0
fi
