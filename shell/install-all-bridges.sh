#!/bin/bash
# install-all-bridges.sh
# 扫描 ~/Workspace/ 下所有项目中的 install-hermes-bridge.sh 并依次执行
# 每个项目脚本负责将自家脚本桥接到 ~/.hermes/scripts/
#
# 桥接方式：创建 wrapper 脚本（非软链），满足 no_agent cron 安全检测

set -euo pipefail

WORKSPACE="${HOME}/Workspace"
HERMES_SCRIPTS="${HOME}/.hermes/scripts"
RUN_LEGACY_INSTALLERS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --legacy-installers)
      RUN_LEGACY_INSTALLERS=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$HERMES_SCRIPTS"
COUNT=0

# ── 创建 wrapper 脚本 ──────────────────────────────
# args: source_path target_name
make_wrapper() {
  local src="$1"
  local name="$2"
  local target="${HERMES_SCRIPTS}/${name}"

  if [ ! -f "$src" ] && [ ! -x "$src" ]; then
    echo "  ⚠  ${name} → 源码不存在，跳过"
    return 1
  fi

  if echo "$name" | grep -q '\.py$'; then
    # Python wrapper（cron 用 python3 直接执行，必须合法 Python 语法）
    cat > "$target" << PYWRAP
#!/usr/bin/env python3
"""Thin wrapper — delegates to canonical script."""
import runpy
import sys

_REAL = "${src}"
sys.argv[0] = _REAL
runpy.run_path(_REAL, run_name="__main__")
PYWRAP
  else
    # Shell / 二进制 wrapper
    cat > "$target" << SHWRAP
#!/bin/bash
exec "${src}" "\$@"
SHWRAP
  fi

  chmod +x "$target"
}

# ── 阶段1: 运行各项目 bridge 脚本（保留向后兼容） ─
echo "━━━ Phase 1: 项目桥接 ━━━"
echo ""

if [ "$RUN_LEGACY_INSTALLERS" -eq 1 ]; then
  echo "  legacy installer mode enabled"
  for installer in "$WORKSPACE"/*/scripts/install-hermes-bridge.sh; do
    if [ -f "$installer" ] && [ -x "$installer" ]; then
      project=$(echo "$installer" | sed "s|$WORKSPACE/||" | cut -d/ -f1)
      echo "  [${project}]"
      "$installer" 2>&1 | sed 's/^/    /' || true
      COUNT=$((COUNT + 1))
      echo ""
    fi
  done
else
  echo "  wrapper-only mode: skipping legacy install-hermes-bridge.sh scanners"
  echo ""
fi

# ── 阶段2: 将软链替换为 wrapper ─────────────────
echo "━━━ Phase 2: 软链 → Wrapper 转换 ━━━"
echo ""

CONVERTED=0
BROKEN=0
for link in "$HERMES_SCRIPTS"/*; do
  [ ! -L "$link" ] && continue
  target=$(readlink "$link")
  bn=$(basename "$link")

  if echo "$target" | grep -q "^$WORKSPACE"; then
    # 在脚本目录内→保留软链
    rm "$link"
    make_wrapper "$target" "$bn"
    CONVERTED=$((CONVERTED + 1))
  else
    # 指向脚本目录外的→也要转
    rm "$link"
    make_wrapper "$target" "$bn"
    CONVERTED=$((CONVERTED + 1))
  fi
done

echo "  转换 ${CONVERTED} 个软链为 wrapper"
echo ""

# ── 阶段3: 统计 ──────────────────────────────────
echo "━━━ 桥接清单 ━━━"
WRAPPER_COUNT=0
for f in "$HERMES_SCRIPTS"/*; do
  bn=$(basename "$f")
  [ -d "$f" ] && continue
  echo "$bn" | grep -qE '^(\.|__pycache__|INDEX|SECRETS_INVENTORY)' && continue
  if [ ! -L "$f" ] && [ ! -f "$f" ]; then
    continue
  fi
  # Check if it's a wrapper (script with exec to Workspace)
  if grep -q "exec.*Workspace" "$f" 2>/dev/null; then
    echo "  $(basename "$f") → $(grep 'exec ' "$f" | head -1 | sed 's/.*exec //' | sed 's|$HOME|~|')"
    WRAPPER_COUNT=$((WRAPPER_COUNT + 1))
  fi
done

echo ""
echo "━━━ 完成 ━━━"
echo "  ${COUNT} 个项目桥接完毕"
echo "  ${WRAPPER_COUNT} 个 wrapper 已安装"
