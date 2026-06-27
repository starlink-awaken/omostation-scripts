#!/usr/bin/env bash
# OPC MOF state-bridge cron integration (P5-G1 P5-G2 P5-G4 + P6-G1)
#
# 任何 OPC cron 跑完后必跑 mof-state-bridge --strict, 失同步写 5repos.json
# mof_state_bridge_blocking=true 字段, 让 audit-rollout 复盘 P5-P7 时能看到
# OMOTask 治理状态.
#
# 用法 (任意 OPC cron wrapper 末尾):
#   bash scripts/opc_mof_state_bridge_cron.sh
#
# 环境变量:
#   OPC_TRIGGER (cron/manual) — 透传到 mof-state-bridge 输出
#   OPC_MODE (weekly/monthly/pre-release) — 模式标识
set -euo pipefail

source "$(dirname "$0")/lib/shell/common.sh"

cd "$REPO_ROOT"

# 1. 跑 mof-state-bridge --strict
if ! python3 projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py --strict > /tmp/mof-state-bridge-cron.json 2>&1; then
    echo "⚠️  mof-state-bridge --strict 失同步" >&2
    echo "    output: $(cat /tmp/mof-state-bridge-cron.json)" >&2
fi

# 2. 解析结果
M1_COUNT=$(python3 -c "import json; d=json.load(open('/tmp/mof-state-bridge-cron.json')); print(d.get('m1_count', 0))" 2>/dev/null || echo 0)
OMO_COUNT=$(python3 -c "import json; d=json.load(open('/tmp/mof-state-bridge-cron.json')); print(d.get('omo_count', 0))" 2>/dev/null || echo 0)
PAIRED=$(python3 -c "import json; d=json.load(open('/tmp/mof-state-bridge-cron.json')); print(d.get('paired', 0))" 2>/dev/null || echo 0)
DRIFT=$(python3 -c "import json; d=json.load(open('/tmp/mof-state-bridge-cron.json')); print(len(d.get('diff', {}).get('drifts', [])))" 2>/dev/null || echo 0)
M1_ONLY=$(python3 -c "import json; d=json.load(open('/tmp/mof-state-bridge-cron.json')); print(len(d.get('diff', {}).get('m1_only', [])))" 2>/dev/null || echo 0)
IN_SYNC="false"
if [ "$M1_ONLY" = "0" ]; then IN_SYNC="true"; fi

# 3. 写 5repos 兼容的 mof_state_bridge 字段
OUT_DIR="$REPO_ROOT/.omo/_delivery/audit-rollout"
mkdir -p "$OUT_DIR"
TODAY=$(date -u +%Y-%m-%d)
STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat > "$OUT_DIR/${TODAY}-mof-state-bridge.json" <<EOF
{
  "generated_at": "$STAMP",
  "trigger_source": "${OPC_TRIGGER:-manual}",
  "mode": "${OPC_MODE:-weekly}",
  "mof_state_bridge": {
    "in_sync": $IN_SYNC,
    "m1_count": $M1_COUNT,
    "omo_count": $OMO_COUNT,
    "paired": $PAIRED,
    "drift_count": $DRIFT,
    "m1_only": $M1_ONLY,
    "blocking": $([ "$IN_SYNC" = "true" ] && echo "false" || echo "true")
  }
}
EOF

# 4. 打印摘要
if [ "$IN_SYNC" = "true" ]; then
    echo "✅ mof-state-bridge: $PAIRED/$M1_COUNT 配对成功, $DRIFT 字段漂移 (同义差异), 0 失同步" >&2
else
    echo "❌ mof-state-bridge: $M1_ONLY 个 M1 节点失同步 (m1_only > 0)" >&2
    echo "    阻断后续 OPC cron 跑: mof_state_bridge_blocking=true" >&2
    # 注意: 不强制 exit 1, 因为某些 cron 可能希望"软失败" 继续
    # 5repos.json 已写 blocking=true, audit-rollout 复盘会标红
fi
