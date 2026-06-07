#!/bin/bash
# preserve-m1-files.sh — 守护 M1 Workflow/BOSRoute YAML 文件
# 用法: 作为 pre-commit hook 或 cron job 使用
# 当 workflow 目录文件数 < 20 时，自动从 git 恢复

set -euo pipefail

WORKFLOW_DIR="$HOME/Workspace/projects/ecos/src/ecos/ssot/mof/m1/workflow"
BOSROUTE_DIR="$HOME/Workspace/projects/ecos/src/ecos/ssot/mof/m1/bosroute"
MIN_FILES=20
RESTORE_COMMIT="13a8ee0"

count=$(ls "$WORKFLOW_DIR"/WORKFLOW-*.yaml 2>/dev/null | wc -l | tr -d ' ')
if [ "$count" -lt "$MIN_FILES" ]; then
    echo "[preserve-m1] 检测到 $count 个文件 (< $MIN_FILES)，从 git 恢复..."
    cd "$HOME/Workspace"
    git checkout "$RESTORE_COMMIT" -- projects/ecos/src/ecos/ssot/mof/m1/workflow/ projects/ecos/src/ecos/ssot/mof/m1/bosroute/
    echo "[preserve-m1] 恢复完成"
else
    echo "[preserve-m1] OK: $count 个文件 (>= $MIN_FILES)"
fi
