#!/bin/bash
# uninstall-all-bridges.sh
# 移除 ~/.hermes/scripts/ 下所有指向 ~/Workspace/ 的桥接 wrapper 和软链

set -euo pipefail

WORKSPACE="${HOME}/Workspace"
HERMES_SCRIPTS="${HOME}/.hermes/scripts"

COUNT=0

echo "━━━ uninstall-all-bridges ━━━"
echo ""

for f in "$HERMES_SCRIPTS"/*; do
  bn=$(basename "$f")
  [ -d "$f" ] && continue
  echo "$bn" | grep -qE '^(\.|__pycache__|INDEX|SECRETS_INVENTORY)' && continue

  # 检查：是软链指向 workspace 的
  if [ -L "$f" ]; then
    target=$(readlink "$f")
    if echo "$target" | grep -q "^$WORKSPACE"; then
      echo "  ✗ $bn"
      rm "$f"
      COUNT=$((COUNT + 1))
    fi
  # 检查：是 wrapper（含 exec path 到 workspace 的）
  elif [ -f "$f" ] && [ -x "$f" ]; then
    if head -3 "$f" 2>/dev/null | grep -q "exec.*$WORKSPACE"; then
      echo "  ✗ $bn"
      rm "$f"
      COUNT=$((COUNT + 1))
    fi
  fi
done

echo ""
echo "已移除 ${COUNT} 个桥接"
echo ""
echo "恢复: ~/Workspace/scripts/install-all-bridges.sh"
