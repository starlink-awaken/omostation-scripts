#!/usr/bin/env bash
# debt-leaderboard.sh — 债务排行榜
#
# 按项目展示债务分布，识别高风险项目。

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  债务排行榜${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

# 项目列表
PROJECTS=("kairon" "gbrain" "metaos" "agora" "cockpit" "ecos" "omo" "runtime")

# 表头
printf "%-12s %-10s %-10s %-10s %-10s\n" "项目" "状态" "技术债务" "治理债务" "总分"
echo "────────────────────────────────────────────────────────────"

for proj in "${PROJECTS[@]}"; do
    proj_dir="$REPO_ROOT/projects/$proj"
    
    if [ ! -d "$proj_dir" ]; then
        continue
    fi
    
    # 检查项目状态
    STATUS="✅"
    
    # 检查测试是否存在
    if [ -d "$proj_dir/tests" ]; then
        TEST_COUNT=$(find "$proj_dir/tests" -name "test_*.py" -o -name "*_test.py" 2>/dev/null | wc -l | tr -d ' ')
    else
        TEST_COUNT=0
    fi
    
    # 检查是否有 .githooks/
    if [ -d "$proj_dir/.githooks" ]; then
        HOOKS="✓"
    else
        HOOKS="✗"
        STATUS="⚠️"
    fi
    
    # 检查是否有 pyproject.toml
    if [ -f "$proj_dir/pyproject.toml" ]; then
        HAS_CONFIG="✓"
    else
        HAS_CONFIG="✗"
    fi
    
    # 简单评分
    SCORE=100
    if [ "$TEST_COUNT" -eq 0 ]; then
        SCORE=$((SCORE - 20))
    fi
    if [ "$HOOKS" = "✗" ]; then
        SCORE=$((SCORE - 10))
    fi
    
    # 颜色
    if [ "$SCORE" -ge 90 ]; then
        COLOR="$GREEN"
    elif [ "$SCORE" -ge 70 ]; then
        COLOR="$YELLOW"
    else
        COLOR="$RED"
    fi
    
    printf "%-12s %-10s %-10s %-10s ${COLOR}%-10s${NC}\n" \
        "$proj" "$STATUS" "$TEST_COUNT tests" "$HOOKS hooks" "$SCORE/100"
done

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  评分标准: 测试(-20)  hooks(-10)  配置(-10)${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""
