#!/usr/bin/env bash
# omostation 多仓库统一发布脚本.
#
# 用法:
#   ./scripts/release.sh patch  # 0.1.0 -> 0.1.1
#   ./scripts/release.sh minor  # 0.1.0 -> 0.2.0
#   ./scripts/release.sh major  # 0.1.0 -> 1.0.0
#   ./scripts/release.sh dry    # 仅打印, 不改文件
#
# POC 阶段: 不真 git push, 不打 tag. 只:
#   1. bump VERSION 文件
#   2. 同步各项目 __version__.py
#   3. 更新 CHANGELOG.md
#   4. 提示手动 git 操作
#
# See ADR-0007.

set -euo pipefail

WORKSPACE="${WORKSPACE:-$(cd "$(dirname "$0")/.." && pwd)}"
VERSION_FILE="$WORKSPACE/VERSION"
CHANGELOG="$WORKSPACE/CHANGELOG.md"
PROJECTS=(agora kairon gbrain omo metaos cockpit runtime)
BUMP="${1:-patch}"
DRY=false

if [ "$BUMP" = "dry" ]; then
    DRY=true
    BUMP="patch"
fi

# 读当前版本
if [ ! -f "$VERSION_FILE" ]; then
    echo "0.1.0" > "$VERSION_FILE"
fi
CURRENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')
echo "Current VERSION: $CURRENT"

# 计算新版本
IFS='.' read -r major minor patch <<< "$CURRENT"
case "$BUMP" in
    patch) patch=$((patch + 1)) ;;
    minor) minor=$((minor + 1)); patch=0 ;;
    major) major=$((major + 1)); minor=0; patch=0 ;;
    *) echo "Usage: $0 {patch|minor|major|dry}"; exit 1 ;;
esac
NEW_VERSION="${major}.${minor}.${patch}"
echo "New VERSION: $NEW_VERSION"

if [ "$DRY" = true ]; then
    echo "[dry-run] would set VERSION=$NEW_VERSION and update CHANGELOG"
    echo "[dry-run] would sync: ${PROJECTS[*]}"
    exit 0
fi

# 1. 写 VERSION
echo "$NEW_VERSION" > "$VERSION_FILE"
echo "VERSION -> $NEW_VERSION"

# 2. 同步各项目 __version__.py (POC: 仅 kairon + omo, 物理存在源码)
for proj in kairon omo; do
    version_file="$WORKSPACE/projects/$proj/src/${proj}/__version__.py"
    if [ -f "$version_file" ]; then
        cat > "$version_file" <<EOF
"""$proj version - 引用 omostation 工作区统一版本.

工作区根 VERSION 文件权威 (ADR-0007), 此处只镜像.
"""
from pathlib import Path

_workspace_root = Path(__file__).resolve().parent.parent.parent.parent
try:
    __version__ = (_workspace_root / "VERSION").read_text().strip()
except FileNotFoundError:
    __version__ = "0.0.0"
EOF
        echo "$proj/src/${proj}/__version__.py -> $NEW_VERSION"
    else
        echo "WARN: $version_file missing, skipped"
    fi
done

# 3. 更新 CHANGELOG.md (插入新版本段)
if [ ! -f "$CHANGELOG" ]; then
    cat > "$CHANGELOG" <<EOF
# omostation Changelog

> 多仓库统一发布. 工作区根 VERSION 文件权威.

EOF
fi

# 插入新版本段: 用 awk 在第一个 ## 行前插入新段 (避免重复头部)
DATE=$(date -u +%Y-%m-%d)
NEW_SECTION="## [$NEW_VERSION] - $DATE

### Changed
- Bump version to $NEW_VERSION (release.sh $BUMP)
"
if ! grep -q "^## " "$CHANGELOG"; then
    # 无历史段, append
    printf "\n%s" "$NEW_SECTION" >> "$CHANGELOG"
else
    # 用 awk 在第一个 ## 行前插入
    TMP=$(mktemp)
    awk -v section="$NEW_SECTION" '
        /^## / && !inserted { print section; inserted=1 }
        { print }
    ' "$CHANGELOG" > "$TMP"
    mv "$TMP" "$CHANGELOG"
fi
echo "CHANGELOG.md updated with [$NEW_VERSION]"

# 4. 提示手动 git 操作
echo ""
echo "=== Next steps (manual) ==="
echo "  cd $WORKSPACE"
echo "  git add VERSION CHANGELOG.md projects/*/src/*/__version__.py"
echo "  git commit -m 'release: v$NEW_VERSION'"
echo "  git tag v$NEW_VERSION"
echo "  git push origin main --tags"
echo ""
echo "Release $CURRENT -> $NEW_VERSION (files updated, git ops manual)"
