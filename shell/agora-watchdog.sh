#!/bin/bash
# agora-watchdog — Agora MCP 服务监控 + 自动保活
#
# 每 5 分钟:
#   1. 检查 agora health 是否所有服务正常
#   2. 如果有服务异常，尝试重启
#   3. 清理孤儿进程
#
# 用法: agora-watchdog (由 cron every 5m 调用)

set -euo pipefail

AGORA_BIN="${HOME}/.hermes/hermes-agent/venv/bin/agora"
AGORA_MCP_BIN="${HOME}/.hermes/hermes-agent/venv/bin/agora-mcp"
HEALTH_LOG="${HOME}/.workspace/agora-watchdog.log"

mkdir -p "$(dirname "$HEALTH_LOG")"

# 检查 agora 命令是否可用
if [ ! -x "$AGORA_BIN" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M')] ERROR: agora CLI not found at $AGORA_BIN" >> "$HEALTH_LOG"
  exit 1
fi

# 运行健康检查
HEALTH_OUTPUT=$("$AGORA_BIN" health 2>&1) || true

# 解析结果
UNHEALTHY=$(echo "$HEALTH_OUTPUT" | grep -c "Unhealthy:" || true)
HEALTHY=$(echo "$HEALTH_OUTPUT" | grep "Healthy:" | grep -oP '\d+' | head -1 || echo "0")

if [ "$UNHEALTHY" -gt 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M')] WARNING: $UNHEALTHY unhealthy services detected" >> "$HEALTH_LOG"
  echo "$HEALTH_OUTPUT" >> "$HEALTH_LOG"

  # 尝试重启 Agora MCP
  if [ -x "$AGORA_MCP_BIN" ]; then
    echo "  → Restarting Agora MCP..." >> "$HEALTH_LOG"
    "$AGORA_MCP_BIN" --restart 2>&1 >> "$HEALTH_LOG" || true
  fi
else
  # 正常时每 10 次只记录一次（避免日志膨胀）
  RANDOM_CHECK=$((RANDOM % 10))
  if [ "$RANDOM_CHECK" -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M')] OK: ${HEALTHY}/5 healthy" >> "$HEALTH_LOG"
  fi
fi

# 清理超过 7 天的日志
find "$(dirname "$HEALTH_LOG")" -name "agora-watchdog.log" -mtime +7 -delete 2>/dev/null || true
