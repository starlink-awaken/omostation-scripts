#!/usr/bin/env bash
# P63 plist 试跑脚本 — 一站式 omo + agora 2 plist 启动验证
#
# 步骤:
#   1) plutil 语法 check 2 plist
#   2) dry-run omo serve + agora-mcp 5s (验证 import + parse, 不真启动 daemon)
#   3) cp 2 plist 到 ~/Library/LaunchAgents/
#   4) launchctl load -w 2 plist
#   5) 验证 launchctl list + tail log
#
# 跑法: bash scripts/p63_plist_smoke.sh
# 停 plist: bash scripts/p63_plist_unload.sh (见末尾附)

set -e

WORKSPACE="/Users/xiamingxing/Workspace"
OMO_PROJECT="$WORKSPACE/projects/omo"
AGORA_PROJECT="$WORKSPACE/projects/agora"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
LOG_DIR="$WORKSPACE/.omo/_delivery"

OMO_PLIST_SRC="$OMO_PROJECT/scripts/com.omo.serve.plist"
AGORA_PLIST_SRC="$AGORA_PROJECT/scripts/com.agora.serve.plist"
OMO_PLIST="$LAUNCH_AGENTS/com.omo.serve.plist"
AGORA_PLIST="$LAUNCH_AGENTS/com.agora.serve.plist"

echo "=========================================="
echo "P63 plist 试跑 — omo + agora 2 daemon"
echo "=========================================="

# 步骤 1: plutil 语法 check
echo ""
echo "[Step 1] plutil 语法 check"
plutil -lint "$OMO_PLIST_SRC"
plutil -lint "$AGORA_PLIST_SRC"

# 步骤 2: dry-run (后台跑 5s 看 import, 用 pkill 杀)
echo ""
echo "[Step 2] dry-run omo serve (5s 后 pkill)"
(
  cd "$OMO_PROJECT" && uv run omo serve >/tmp/omo-dryrun-stdout.log 2>/tmp/omo-dryrun-stderr.log &
  OMO_PID=$!
  sleep 5
  kill $OMO_PID 2>/dev/null || true
  wait $OMO_PID 2>/dev/null || true
)
echo "  omo dry-run stdout (前 15 行):"
head -15 /tmp/omo-dryrun-stdout.log 2>/dev/null | sed 's/^/    /' || echo "    (空)"
echo "  omo dry-run stderr (前 10 行):"
head -10 /tmp/omo-dryrun-stderr.log 2>/dev/null | sed 's/^/    /' || echo "    (空)"

echo ""
echo "[Step 2b] dry-run agora-mcp (5s 后 pkill)"
(
  cd "$AGORA_PROJECT" && uv run agora-mcp >/tmp/agora-dryrun-stdout.log 2>/tmp/agora-dryrun-stderr.log &
  AGORA_PID=$!
  sleep 5
  kill $AGORA_PID 2>/dev/null || true
  wait $AGORA_PID 2>/dev/null || true
)
echo "  agora dry-run stdout (前 15 行):"
head -15 /tmp/agora-dryrun-stdout.log 2>/dev/null | sed 's/^/    /' || echo "    (空)"
echo "  agora dry-run stderr (前 10 行):"
head -10 /tmp/agora-dryrun-stderr.log 2>/dev/null | sed 's/^/    /' || echo "    (空)"

# 步骤 3: cp 2 plist 到 LaunchAgents
echo ""
echo "[Step 3] cp 2 plist → ~/Library/LaunchAgents/"
mkdir -p "$LAUNCH_AGENTS"
cp "$OMO_PLIST_SRC" "$OMO_PLIST"
cp "$AGORA_PLIST_SRC" "$AGORA_PLIST"
echo "  ✓ $OMO_PLIST"
echo "  ✓ $AGORA_PLIST"

# 步骤 4: launchctl load -w 2 plist
echo ""
echo "[Step 4] launchctl load -w 2 plist"
launchctl load -w "$OMO_PLIST" && echo "  ✓ com.omo.serve loaded" || echo "  ✗ com.omo.serve load FAILED"
launchctl load -w "$AGORA_PLIST" && echo "  ✓ com.agora.serve loaded" || echo "  ✗ com.agora.serve load FAILED"

# 步骤 5: 验证
echo ""
echo "[Step 5] 验证 launchctl list"
launchctl list 2>&1 | grep -E "com.omo.serve|com.agora.serve" | head -5 || echo "  (没找到 — 可能启动失败)"

echo ""
echo "[Step 5b] log 末尾 (各 20 行)"
echo "  --- omo stdout ---"
tail -20 "$LOG_DIR/omo-serve-stdout.log" 2>/dev/null | sed 's/^/    /' || echo "    (log 不存在)"
echo "  --- omo stderr ---"
tail -20 "$LOG_DIR/omo-serve-stderr.log" 2>/dev/null | sed 's/^/    /' || echo "    (log 不存在)"
echo "  --- agora stdout ---"
tail -20 "$LOG_DIR/agora-serve-stdout.log" 2>/dev/null | sed 's/^/    /' || echo "    (log 不存在)"
echo "  --- agora stderr ---"
tail -20 "$LOG_DIR/agora-serve-stderr.log" 2>/dev/null | sed 's/^/    /' || echo "    (log 不存在)"

echo ""
echo "=========================================="
echo "P63 plist 试跑完成"
echo "=========================================="
echo ""
echo "卸载 plist (按需):"
echo "  launchctl unload $OMO_PLIST"
echo "  launchctl unload $AGORA_PLIST"
