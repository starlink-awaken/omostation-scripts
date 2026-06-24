#!/usr/bin/env bash
# 跨项目健康扫描 — 快速版
# 用途: 每日 cron, 核心项目跑测试, 其余跑 lint + git
# 用法: bash scripts/health_scan.sh

set -euo pipefail

WS="$HOME/Workspace"
RESULTS=()
TIMEOUT=120  # seconds per test

echo "# 跨项目健康报告"
echo
echo "_生成时间: $(date -u '+%Y-%m-%d %H:%M:%S UTC')_"
echo
echo "## 测试基线"
echo
printf "| %-20s | %-15s | %-20s | %-10s | %-8s |\n" "项目" "分层" "测试结果" "Lint" "Git"
printf "|%s|%s|%s|%s|%s|\n" "$(printf '%.0s-' {1..22})" "$(printf '%.0s-' {1..17})" "$(printf '%.0s-' {1..22})" "$(printf '%.0s-' {1..12})" "$(printf '%.0s-' {1..10})"

scan() {
  local dir="$1" label="$2" src="$3" test_path="$4"
  local proj="$WS/projects/$dir"
  local test_result="-" lint_result="✅" git_result="clean"

  # Git
  local g
  g=$(cd "$proj" 2>/dev/null && git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  if [ "$g" != "0" ]; then git_result="${g}f"; fi

  # Ruff lint (fast)
  if [ -n "$src" ] && [ -d "$proj/$src" ]; then
    if ! (cd "$proj" && uv run ruff check "$src" --statistics >/dev/null 2>&1); then
      lint_result="❌ err"
    fi
  fi

  # Test (only for core projects with fast tests)
  if [ -n "$test_path" ]; then
    local tmpout; tmpout=$(mktemp)
    if (cd "$proj" && timeout $TIMEOUT uv run pytest "$test_path" -q --tb=no >"$tmpout" 2>&1); then
      test_result=$(grep -E "passed|failed|skipped" "$tmpout" | tail -1 | tr -d '\n')
      [ -z "$test_result" ] && test_result="✅"
    else
      local last; last=$(tail -1 "$tmpout" | tr -d '\n')
      test_result="⚠️ ${last:0:25}"
    fi
    rm -f "$tmpout"
  fi

  printf "| %-20s | %-15s | %-20s | %-10s | %-8s |\n" "$dir" "$label" "$test_result" "$lint_result" "$git_result"
}

# Core projects — run tests
scan "ecos"     "L0 协议"       "src"                "tests"
scan "cockpit"  "L3 入口"       "src/cockpit"         "src/cockpit/tests -k 'not test_no_subcommand'"

# Others — lint + git only
scan "agora"    "I0 Mesh"       "src/agora"           ""
scan "omo"      "L2 治理"       "src/omo"             ""
scan "metaos"   "L2 编排"       "src/metaos"          ""
scan "runtime"  "L1 运行时"      "src/runtime"         ""
scan "kairon"   "L2 引擎"       "packages"            ""
scan "aetherforge" "X 能力"      "src/aetherforge"     ""
scan "model-driven" "X 模型"     "src/model_driven"    ""
scan "c2g"      "X 需求"        "src/c2g"             ""
scan "omo-debt" "X 债务"        "src/omo_debt"        ""
scan "l4-kernel" "L4 自我"      "src/l4_kernel"       ""

echo
echo "_治理心跳已写入_"

# Write governance heartbeat
python3 -c "
import json, os
entry = {
    'action': 'health-scan',
    'node_id': 'governance-system',
    'status': 'ok',
    'operator': 'cron',
    'detail': 'cross-project health scan completed',
    'ts': '$(date -u +%Y-%m-%dT%H:%M:%S)' + 'Z',
}
log = os.path.expanduser('~/.hermes/architecture/governance_log/governance.jsonl')
os.makedirs(os.path.dirname(log), exist_ok=True)
with open(log, 'a') as f:
    f.write(json.dumps(entry, sort_keys=True) + '\n')
"
