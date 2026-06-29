#!/usr/bin/env bash
# P66 plist 重试脚本 — 验证 P65-W0 2 plist KeepAlive 复杂化效果
#
# 步骤:
#   1) 卸载 P63 load 的旧 plist (P65 项目内 plist 已改, 但 ~/Library 没更新)
#   2) rm 旧 plist + cp 新 plist 到 ~/Library/LaunchAgents/
#   3) launchctl load -w 2 plist
#   4) 等 30s (agora 16 service 启动时间)
#   5) launchctl list 验证 + tail log
#
# 跑法: bash scripts/p66_plist_retry.sh
# 停 plist: bash scripts/p63_plist_unload.sh (见 P63 卡)

set -e

source "$(dirname "$0")/lib/shell/common.sh"

WORKSPACE="$REPO_ROOT"
OMO_PROJECT="$WORKSPACE/projects/omo"
AGORA_PROJECT="$WORKSPACE/projects/agora"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
LOG_DIR="$WORKSPACE/.omo/_delivery"

OMO_PLIST_SRC="$OMO_PROJECT/scripts/com.omo.serve.plist"
AGORA_PLIST_SRC="$AGORA_PROJECT/scripts/com.agora.serve.plist"
OMO_PLIST="$LAUNCH_AGENTS/com.omo.serve.plist"
AGORA_PLIST="$LAUNCH_AGENTS/com.agora.serve.plist"

echo "=========================================="
echo "P66 plist 重试 — 验证 P65-W0 KeepAlive 复杂化"
echo "=========================================="

# 步骤 1: 卸载旧 plist (P63 时 load 的)
echo ""
echo "[Step 1] unload 旧 plist (P63 时 load 的, P65 项目内 plist 已改)"
if launchctl list 2>/dev/null | grep -q "com.omo.serve"; then
  launchctl unload "$OMO_PLIST" && echo "  ✓ com.omo.serve unloaded" || echo "  ⚠ unload failed (可能没在跑)"
else
  echo "  ⏭️  com.omo.serve 没在跑, 跳过 unload"
fi
if launchctl list 2>/dev/null | grep -q "com.agora.serve"; then
  launchctl unload "$AGORA_PLIST" && echo "  ✓ com.agora.serve unloaded" || echo "  ⚠ unload failed"
else
  echo "  ⏭️  com.agora.serve 没在跑, 跳过 unload"
fi

# 步骤 2: rm 旧 plist + cp 新 plist (P65-W0 改后版本)
echo ""
echo "[Step 2] rm 旧 plist + cp 新 plist (P65-W0 改后版本)"
if [ -f "$OMO_PLIST" ]; then
  rm -f "$OMO_PLIST" && echo "  ✓ rm 旧 com.omo.serve.plist"
fi
if [ -f "$AGORA_PLIST" ]; then
  rm -f "$AGORA_PLIST" && echo "  ✓ rm 旧 com.agora.serve.plist"
fi
cp "$OMO_PLIST_SRC" "$OMO_PLIST" && echo "  ✓ cp 新 com.omo.serve.plist"
cp "$AGORA_PLIST_SRC" "$AGORA_PLIST" && echo "  ✓ cp 新 com.agora.serve.plist"

# 步骤 3: launchctl load -w 2 plist
echo ""
echo "[Step 3] launchctl load -w 2 plist (P65-W0 KeepAlive 复杂化版本)"
launchctl load -w "$OMO_PLIST" && echo "  ✓ com.omo.serve loaded (KeepAlive 复杂化)" || echo "  ✗ com.omo.serve load FAILED"
launchctl load -w "$AGORA_PLIST" && echo "  ✓ com.agora.serve loaded (KeepAlive 复杂化)" || echo "  ✗ com.agora.serve load FAILED"

# 步骤 4: 等 30s (agora 16 service bootstrap + 4 kairon 包 stdin EOF sleep+retry 启动)
echo ""
echo "[Step 4] 等 30s (agora 16 service bootstrap + kairon 4 包 daemon_mode 启动)"
sleep 30

# 步骤 5: 验证
echo ""
echo "[Step 5] launchctl list 实时状态"
launchctl list 2>&1 | grep -E "com.omo.serve|com.agora.serve" | head -5

echo ""
echo "[Step 5b] omo stderr log 末尾 (15 行)"
tail -15 "$LOG_DIR/omo-serve-stderr.log" 2>/dev/null | sed 's/^/    /' || echo "    (log 不存在)"

echo ""
echo "[Step 5c] agora stdout log 末尾 (15 行)"
tail -15 "$LOG_DIR/agora-serve-stdout.log" 2>/dev/null | sed 's/^/    /' || echo "    (log 不存在)"

echo ""
echo "[Step 5d] agora stderr log 末尾 (10 行)"
tail -10 "$LOG_DIR/agora-serve-stderr.log" 2>/dev/null | sed 's/^/    /' || echo "    (log 不存在)"

echo ""
echo "[Step 5e] agora 16 proxy service 健康度统计"
CONNECTED=$(grep -c "proxy_service_connected" "$LOG_DIR/agora-serve-stdout.log" 2>/dev/null || echo 0)
FAILED=$(grep -c "proxy_service_connect_failed" "$LOG_DIR/agora-serve-stdout.log" 2>/dev/null || echo 0)
NOT_FOUND=$(grep -c "proxy_subprocess_not_found" "$LOG_DIR/agora-serve-stdout.log" 2>/dev/null || echo 0)
echo "  connected:    $CONNECTED service"
echo "  connect_failed: $FAILED service"
echo "  not_found:    $NOT_FOUND service (command 不在 PATH)"

echo ""
echo "=========================================="
echo "P66 plist 重试完成"
echo "=========================================="
echo ""
echo "完全卸载 (恢复 P63 试跑前):"
echo "  launchctl unload $OMO_PLIST"
echo "  launchctl unload $AGORA_PLIST"
echo "  rm $OMO_PLIST $AGORA_PLIST"
