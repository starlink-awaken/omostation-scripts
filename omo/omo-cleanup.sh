#!/usr/bin/env bash
# ──────────────────────────────────────────────
# omo-cleanup — 定期清理 .omo/ 运行时垃圾
# 被 Hermes cron 调用，周期：每天一次
# ──────────────────────────────────────────────
set -euo pipefail

OMO_DIR="${1:-$HOME/Workspace/.omo}"
LOG="$HOME/runtime/logs/omo-cleanup.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$(dirname "$LOG")"

# 只清理 .gitignore 规则中明确忽略的运行时目录
# 绝不触碰 git track 中的治理配置

cleaned=0
for dir in workers _delivery debt plans run-continuation; do
    target="$OMO_DIR/$dir"
    if [ -d "$target" ]; then
        size=$(du -sh "$target" 2>/dev/null | awk '{print $1}')
        rm -rf "$target" 2>/dev/null || true
        echo "[$TIMESTAMP] ✅ $dir/ — 已删除 (was $size)" >> "$LOG"
        cleaned=$((cleaned + 1))
    fi
done

# 清理 _knowledge/*.jsonl（保留 governance-history.jsonl，有审计价值）
if [ -d "$OMO_DIR/_knowledge" ]; then
    find "$OMO_DIR/_knowledge" -maxdepth 1 -name '*.jsonl' \
        ! -name 'governance-history.jsonl' \
        -mtime +1 -delete 2>/dev/null || true
    echo "[$TIMESTAMP] ✅ _knowledge/*.jsonl — 清理过期(>1d)" >> "$LOG"
fi

# 清理 __pycache__ 碎片
find "$OMO_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "[$TIMESTAMP] ✅ 完成，清理 $cleaned 个目录" >> "$LOG"
