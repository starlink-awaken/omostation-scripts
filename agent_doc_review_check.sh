#!/usr/bin/env bash
# agent_doc_review_check.sh — 检查最近 git commit 影响的 agent 文档 (P73-W2 配 P71-W2)
#
# 跟 P71-W2 post_commit_update_agent_docs.sh 镜像 (omostation 仓内脚本):
# - 读 ~/.omo/_delivery/agent_doc_update.log (P71-W2 hook 写的)
# - 列出最近 N 个 commit (默认 5) 受影响的 agent docs (CLAUDE.md/AGENTS.md/README.md)
# - 提示 manual review
#
# 用法:
#   bash scripts/agent_doc_review_check.sh           # 默认最近 5 commit
#   bash scripts/agent_doc_review_check.sh 10        # 最近 10 commit
#   bash scripts/agent_doc_review_check.sh --help    # 帮助

set -e

LOG="$HOME/.omo/_delivery/agent_doc_update.log"
N=${1:-5}

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "用法: bash scripts/agent_doc_review_check.sh [N]"
    echo ""
    echo "N: 列出最近 N 个 commit 受影响的 agent 文档 (默认 5)"
    echo "log: $LOG (P71-W2 post_commit hook 写)"
    echo ""
    echo "例:"
    echo "  bash scripts/agent_doc_review_check.sh    # 最近 5"
    echo "  bash scripts/agent_doc_review_check.sh 10 # 最近 10"
    exit 0
fi

if [ ! -f "$LOG" ]; then
    echo "[agent_doc_review] log 不存在: $LOG"
    echo "  (P71-W2 hook 没触发过 commit, 或 ~/.omo/_delivery/ 不可写)"
    exit 0
fi

echo "=========================================="
echo "agent_doc_review — 最近 $N 个 commit 受影响 agent 文档"
echo "=========================================="
echo ""

# 取最近 N 个 commit 段 (用 awk 分隔 "=====" 行)
awk -v n="$N" '
    /^===== / { count++; if (count > n) exit }
    { print }
' "$LOG" | tail -200

echo ""
echo "=========================================="
echo "[提示] 改完 doc 后 commit, hook 自动 update log"
echo "=========================================="
