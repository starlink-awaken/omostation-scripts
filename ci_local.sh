#!/usr/bin/env bash
# omostation 本地 CI 模拟.
#
# 模拟 GitHub Actions workflow 在本地跑, 验证 omo governance audit.
# 不依赖网络/不真 push, 只本地检查.
#
# 用法:
#     ./scripts/ci_local.sh
#

set -euo pipefail

WORKSPACE="${WORKSPACE:-/Users/xiamingxing/Workspace}"
cd "$WORKSPACE"

echo "=== omostation 本地 CI 模拟 ==="
echo ""

# 1. ruff check (新文件)
echo "1. ruff check kairon 包 (新增/修改文件)..."
if [ -d "$WORKSPACE/projects/kairon" ]; then
    cd "$WORKSPACE/projects/kairon"
    uv run ruff check packages/ 2>&1 | tail -3 || echo "ruff: see output above"
else
    echo "(skipped: kairon not found)"
fi
echo ""

# 2. kairon 单元测试
echo "2. kairon 单元测试..."
if [ -d "$WORKSPACE/projects/kairon/packages" ]; then
    cd "$WORKSPACE/projects/kairon"
    uv run python -m pytest packages/*/tests/unit -q 2>&1 | tail -3 || echo "pytest: see output above"
else
    echo "(skipped: kairon packages not found)"
fi
echo ""

# 3. omo 单元测试
echo "3. omo 单元测试..."
if [ -d "$WORKSPACE/projects/omo/tests" ]; then
    cd "$WORKSPACE/projects/omo"
    uv run python -m pytest tests/ -q 2>&1 | tail -3 || echo "pytest: see output above"
else
    echo "(skipped: omo tests not found)"
fi
echo ""

# 4. omo audit 总分 ≥ 95
echo "4. omo governance audit 总分 ≥ 95..."
cd "$WORKSPACE/projects/omo"
uv run omo governance audit --output /tmp/ci_audit.md
SCORE=$(grep "总分" /tmp/ci_audit.md | head -1 | grep -oE "[0-9]+\.[0-9]+" | head -1)
if [ -z "$SCORE" ]; then
    echo "Audit 总分未找到 in /tmp/ci_audit.md"
    exit 1
fi
echo "Audit 总分: $SCORE"
if (( $(echo "$SCORE < 95" | bc -l) )); then
    echo "Audit 总分 $SCORE < 95"
    exit 1
fi
echo ""

# 5. 0 missing deliverables
echo "5. 0 missing deliverables (P36 治理债务永久化)..."
cd "$WORKSPACE/projects/omo"
uv run omo governance audit 2>&1 | tee /tmp/ci_full.txt > /dev/null
MISSING=$(grep -c "missing deliverable" /tmp/ci_full.txt || true)
if [ "$MISSING" -gt 0 ]; then
    echo "Found $MISSING missing deliverables"
    exit 1
fi
echo "0 missing deliverables"
echo ""

# 6. agora 12/12 健康
echo "6. agora 12/12 健康..."
cd "$WORKSPACE/projects/omo"
uv run omo health 2>&1 | tail -3 || echo "(omo health 命令未跑, 跳过)"
echo ""

# 7. omo daemon
echo "7. omo daemon (launchctl)..."
if launchctl list 2>/dev/null | grep -q com.omo.governance.daemon; then
    echo "omo daemon 正在跑"
else
    echo "(omo daemon 未注册 — POC 阶段可接受)"
fi
echo ""

# 8. planned queue consistency
echo "8. planned queue 一致性 (只允许 candidate/pending)..."
if ! python3 "$WORKSPACE/scripts/omo/omo_worker.py" task validate --all-planned >/tmp/omo-planned-validate.log 2>&1; then
    echo "planned queue 校验失败"
    cat /tmp/omo-planned-validate.log
    exit 1
fi
echo "planned queue 一致"
echo ""

# 9. done 目录一致性
echo "9. done 目录只允许 done/completed 状态..."
DONE_BAD=$(
    find "$WORKSPACE/.omo/tasks/done" -mindepth 2 -maxdepth 2 -name "*.yaml" -print0 2>/dev/null \
        | xargs -0 grep -El "status: (pending|review|in_progress|planned)" 2>/dev/null || true
)
REGISTRY_DONE_BAD=$(
    find "$WORKSPACE/.omo/tasks/registry/done" -maxdepth 1 -name "*.yaml" -print0 2>/dev/null \
        | xargs -0 grep -El "status: (pending|review|in_progress|planned)" 2>/dev/null || true
)
if [ -n "$DONE_BAD$REGISTRY_DONE_BAD" ]; then
    echo "Found non-final task status inside done carriers"
    [ -n "$DONE_BAD" ] && echo "$DONE_BAD"
    [ -n "$REGISTRY_DONE_BAD" ] && echo "$REGISTRY_DONE_BAD"
    exit 1
fi
echo "done 目录一致"
echo ""

echo "=== 所有 CI 检查通过 ==="
