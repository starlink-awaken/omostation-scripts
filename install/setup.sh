#!/usr/bin/env bash
# setup.sh — 从 0 到跑通: 初始化 omostation 工作站
# 用法: git clone --recursive <root-repo> && cd omostation && bash scripts/install/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "╔═══════════════════════════════════════════╗"
echo "║  omostation 初始化向导                     ║"
echo "╚═══════════════════════════════════════════╝"

echo ""
echo "── 1. 安装核心项目依赖 ──"
for proj in cockpit agora runtime kairon metaos ecos omo; do
  echo "  [uv sync] projects/$proj..."
  (cd "$ROOT/projects/$proj" && uv sync --quiet 2>&1 | tail -1)
done
echo "  ✅ 依赖安装完成"

echo ""
echo "── 2. 验证 CLI ──"
for cmd in cockpit workspace agora runtime; do
  if command -v "$cmd" &>/dev/null; then
    echo "  ✅ $cmd 可用"
  elif [ -x "$ROOT/bin/$cmd" ]; then
    echo "  ✅ $cmd (via bin/)"
  else
    echo "  ⚠️  $cmd 需手动: pip install -e projects/xxx"
  fi
done

echo ""
echo "── 3. 服务状态 ──"
echo "  启动方式:"
echo "    agora SSE :7431   →  cd projects/agora && uv run python -m agora.server.mcp"
echo "    cron-service :7450 → cd projects/runtime && uv run python -m runtime.cron_service"
echo ""

echo "── 4. 验证测试 ──"
echo "  cd projects/kairon && uv run pytest packages/eidos -q    # 272 测试"
echo "  cd projects/cockpit && uv run pytest src/cockpit/tests -q  # 562 测试"
echo "  cd projects/ecos && uv run pytest tests -q                # 195 测试"
echo ""

echo "── 5. 快速体验 ──"
echo "  cd $ROOT && bin/workspace demo"
echo "  cd $ROOT && bin/workspace status"
echo "  cd $ROOT && bin/workspace research '你的主题'"
echo ""

echo "╔═══════════════════════════════════════════╗"
echo "║  初始化完成! 3 条命令跑完以上全部:           ║"
echo "║                                            ║"
echo "║  git clone --recursive <url>               ║"
echo "║  cd omostation && bash scripts/install/setup ║"
echo "║  bin/workspace demo                        ║"
echo "╚═══════════════════════════════════════════╝"
