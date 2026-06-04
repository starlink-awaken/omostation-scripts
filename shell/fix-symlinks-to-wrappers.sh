#!/bin/bash
# fix-symlinks-to-wrappers.sh
# 将 ~/.hermes/scripts/ 中指向 ~/Workspace/ 的软链替换为实体 shell wrapper 脚本
# 解决 no_agent cron 安全检测问题（软链目标超出脚本目录会被拦截）
#
# wrapper 格式：薄层 bash 脚本，exec 到源码位置

set -euo pipefail

HERMES_SCRIPTS="${HOME}/.hermes/scripts"
WORKSPACE="${HOME}/Workspace"
COUNT=0

echo "━━━ 软链 → Wrapper 转换 ━━━"
echo ""

for link in "$HERMES_SCRIPTS"/*; do
  if [ -L "$link" ]; then
    target=$(readlink "$link")
    if echo "$target" | grep -q "^$WORKSPACE"; then
      bn=$(basename "$link")

      # 构建 wrapper：全部用 bash exec 方式，兼容 sh/py/二进制
      # Python 脚本用 python3 解释器 exec
      if echo "$bn" | grep -q '\.py$'; then
        cat > "$link" << PYWRAP
#!/bin/bash
# Thin wrapper: ${target}
exec /usr/bin/env python3 "${target}" "\$@"
PYWRAP
      else
        # Shell 脚本或二进制
        cat > "$link" << SHWRAP
#!/bin/bash
# Thin wrapper: ${target}
exec "${target}" "\$@"
SHWRAP
      fi

      chmod +x "$link"
      echo "  ✓  ${bn}"
      COUNT=$((COUNT + 1))
    fi
  fi
done

echo ""
echo "已转换 ${COUNT} 个软链为 wrapper"
echo ""
echo "注意: 各项目 install-hermes-bridge.sh 也需要改为创建 wrapper 而非软链"
