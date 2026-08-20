#!/usr/bin/env bash
# submodule-autobump.sh — 自动 bump 子模块指针到最新 origin/main
#
# 检测所有子模块, 如果 origin/main 前进了, 自动更新指针并开 PR.
# 设计为 GitHub Actions schedule 或 cron 调用.
#
# 用法:
#   bash bin/ssot/submodule-autobump.sh              # 自动 bump + 开 PR
#   bash bin/ssot/submodule-autobump.sh --check-only  # 只检查不修改
#   bash bin/ssot/submodule-autobump.sh --dry-run    # 只显示将要做的修改

set -euo pipefail

DRY_RUN=false
CHECK_ONLY=false
case "${1:-}" in
  --dry-run) DRY_RUN=true ;;
  --check-only) CHECK_ONLY=true ;;
esac

WS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -z "$WS_ROOT" ] && { echo "❌ 不在 git 仓库" >&2; exit 1; }
cd "$WS_ROOT"

echo "=== Submodule Autobump $(date -u +%Y-%m-%dT%H:%M:%Z) ==="

# 获取所有子模块
SUBMODULES=$(git config --file .gitmodules --get-regexp path 2>/dev/null | awk '{print $2}')
[ -z "$SUBMODULES" ] && { echo "✅ 没有子模块"; exit 0; }

bumped=0
for sub in $SUBMODULES; do
  [ -e "$sub/.git" ] || continue

  # 当前指针
  current_sha=$(git ls-files --stage -- "$sub" | awk '{print $2}')
  [ -n "$current_sha" ] || continue

  # 获取最新 origin/main
  latest_sha=$(git -C "$sub" rev-parse origin/main 2>/dev/null)
  [ -n "$latest_sha" ] || continue

  if [ "$current_sha" = "$latest_sha" ]; then
    continue
  fi

  # 检查是否可达 (避免指向不存在的 commit)
  if ! git -C "$sub" cat-file -e "$latest_sha" 2>/dev/null; then
    echo "⚠️  $sub: origin/main ($latest_sha) 不可达, 跳过"
    continue
  fi

  echo "🔄 $sub: ${current_sha:0:8} → ${latest_sha:0:8}"

  if [ "$DRY_RUN" = true ] || [ "$CHECK_ONLY" = true ]; then
    bumped=$((bumped + 1))
    continue
  fi

  # 更新 index
  git update-index --cacheinfo 160000,"$latest_sha","$sub"
  bumped=$((bumped + 1))
done

echo "---"
echo "需要 bump: $bumped 个子模块"

if [ "$DRY_RUN" = false ] && [ "$CHECK_ONLY" = false ] && [ "$bumped" -gt 0 ]; then
  # 提交并推送
  # 注意: 不能在这里 `git add .` —— 子模块已 checkout 到工作树时, git add 会用
  # 工作树的旧指针覆盖上方 update-index 写入的新指针, 导致 nothing to commit.
  # update-index 已把新指针写入 index, 直接 commit 即可 (与 root 版 submodule-autobump.sh 一致).
  git commit -m "chore: auto-bump $bumped submodule pointers to latest main"
  echo "✅ 已提交 bump"
fi

[ "$CHECK_ONLY" = true ] && [ "$bumped" -gt 0 ] && exit 1
exit 0
