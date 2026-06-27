#!/usr/bin/env bash
# common.sh — shell 脚本共享基础设施。
#
# 消除 5+ 处颜色 helper + REPO_ROOT 发现 + pass/warn/fail 复制。
#
# 用法 (在脚本顶部):
#   source "$(dirname "$0")/lib/shell/common.sh"
#
# 或从 omo/ 子目录:
#   source "$(dirname "$0")/../lib/shell/common.sh"

set -euo pipefail

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── 计数器 ──
ERRORS=0
WARNINGS=0

# ── workspace root 发现 ──
# 1. $WORKSPACE_ROOT 环境变量
# 2. 从 scripts/ 目录推导 (scripts/ 的父目录)
# 3. $HOME/Workspace (最后手段)
discover_workspace_root() {
    if [[ -n "${WORKSPACE_ROOT:-}" && -d "${WORKSPACE_ROOT}/.omo" ]]; then
        echo "${WORKSPACE_ROOT}"
        return
    fi

    # 推导: common.sh 在 scripts/lib/shell/ 下
    # scripts/lib/shell/common.sh → parents[3] = workspace root
    local common_sh="${BASH_SOURCE[0]}"
    local script_dir
    script_dir="$(cd "$(dirname "$common_sh")" && pwd)"
    local scripts_dir
    scripts_dir="$(dirname "$(dirname "$script_dir")")"  # scripts/
    local ws_root
    ws_root="$(dirname "$scripts_dir")"  # workspace root

    if [[ -d "${ws_root}/.omo" ]]; then
        echo "${ws_root}"
        return
    fi

    # 最后手段
    if [[ -d "${HOME}/Workspace/.omo" ]]; then
        echo "${HOME}/Workspace"
        return
    fi

    echo "ERROR: 无法定位 workspace root" >&2
    exit 1
}

REPO_ROOT="${WORKSPACE_ROOT:-$(discover_workspace_root)}"
OMO_DIR="${REPO_ROOT}/.omo"
TRUTH_DIR="${OMO_DIR}/_truth"
KNOWLEDGE_DIR="${OMO_DIR}/_knowledge"
DELIVERY_DIR="${OMO_DIR}/_delivery"

# ── 输出 helper ──
pass() {
    echo -e "  ${GREEN}✓${NC} $1"
}

warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

fail() {
    echo -e "  ${RED}✗${NC} $1"
    ERRORS=$((ERRORS + 1))
}

info() {
    echo -e "  ${CYAN}ℹ${NC} $1"
}

section() {
    echo ""
    echo -e "${BOLD}━━ $1 ━━${NC}"
}

# ── 退出汇总 ──
exit_summary() {
    echo ""
    if [[ $ERRORS -gt 0 ]]; then
        echo -e "${RED}FAILED${NC}: ${ERRORS} errors, ${WARNINGS} warnings"
        exit 1
    elif [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}PASSED${NC} with ${WARNINGS} warnings"
        exit 0
    else
        echo -e "${GREEN}PASSED${NC}"
        exit 0
    fi
}
