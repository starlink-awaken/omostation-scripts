#!/bin/bash
# Workspace每日备份脚本
# 版本: v1.0
# 创建日期: 2026-05-24
# 用途: 备份关键数据和配置

set -e  # 遇到错误立即退出

# 配置
WORKSPACE="/Users/xiamingxing/Workspace"
BACKUP_BASE_DIR="${WORKSPACE}/backups"
BACKUP_DIR="${BACKUP_BASE_DIR}/daily/$(date +%Y%m%d)"
RETENTION_DAYS=30  # 保留30天的备份

# 创建备份目录
mkdir -p "$BACKUP_DIR"

echo "=== Workspace每日备份 ==="
echo "备份目录: $BACKUP_DIR"
echo "备份时间: $(date)"
echo ""

# 备份函数
backup_file() {
    local source="$1"
    local dest="$2"
    
    if [ -e "$source" ]; then
        echo "备份: $source"
        cp -r "$source" "$dest"
        echo "  ✅ 完成"
    else
        echo "  ⚠️  文件不存在，跳过"
    fi
}

backup_dir() {
    local source="$1"
    local dest="$2"
    
    if [ -d "$source" ]; then
        echo "备份目录: $source"
        rsync -av "$source" "$dest" --delete
        echo "  ✅ 完成"
    else
        echo "  ⚠️  目录不存在，跳过"
    fi
}

# 备份SQLite数据库
echo "--- SQLite数据库备份 ---"
backup_file "$WORKSPACE/agora/agora.db" "$BACKUP_DIR/agora.db"
backup_file "$WORKSPACE/agentmesh/data/gateway.db" "$BACKUP_DIR/agentmesh.db" 2>/dev/null || true

# 备份向量数据库
echo ""
echo "--- 向量数据库备份 ---"
backup_dir "$WORKSPACE/minerva/data/lancedb" "$BACKUP_DIR/lancedb"

# 备份配置文件
echo ""
echo "--- 配置文件备份 ---"
CONFIG_TAR="$BACKUP_DIR/configs.tar.gz"
tar -czf "$CONFIG_TAR" \
    -C "$WORKSPACE" \
    agentmesh/config/*.yaml \
    agora/*.yaml \
    minerva/config/*.yaml \
    ontoderive/*.yaml \
    2>/dev/null || echo "  ⚠️  配置文件备份失败"

if [ -f "$CONFIG_TAR" ]; then
    echo "  ✅ 配置文件备份完成"
fi

# 备份日志文件
echo ""
echo "--- 日志文件备份 ---"
LOG_TAR="$BACKUP_DIR/logs.tar.gz"
find "$WORKSPACE" -name "*.log" -type f | head -100 | xargs tar -czf "$LOG_TAR" 2>/dev/null || echo "  ⚠️  日志文件备份失败"

if [ -f "$LOG_TAR" ]; then
    echo "  ✅ 日志文件备份完成"
fi

# 备份文档
echo ""
echo "--- 文档备份 ---"
DOC_TAR="$BACKUP_DIR/docs.tar.gz"
tar -czf "$DOC_TAR" \
    -C "$WORKSPACE" \
    ARCHITECTURE.md \
    AGENTS.md \
    PRODUCT_VISION.md \
    CONTRACTS.md \
    CAPABILITIES.md \
    README.md \
    2>/dev/null || echo "  ⚠️  文档备份失败"

if [ -f "$DOC_TAR" ]; then
    echo "  ✅ 文档备份完成"
fi

# 备份用户数据
echo ""
echo "--- 用户数据备份 ---"
backup_dir "$WORKSPACE/workspace/data" "$BACKUP_DIR/user-data" 2>/dev/null || true
backup_dir "$WORKSPACE/Forge" "$BACKUP_DIR/forge-data" 2>/dev/null || true

# 生成备份清单
echo ""
echo "--- 生成备份清单 ---"
MANIFEST="$BACKUP_DIR/manifest.txt"
cat > "$MANIFEST" <<EOF
备份时间: $(date)
备份类型: 每日备份
备份内容:
EOF

# 添加文件清单
find "$BACKUP_DIR" -type f -not -name "manifest.txt" | while read -r file; do
    size=$(du -h "$file" | cut -f1)
    checksum=$(md5 "$file" | cut -d' ' -f4)
    echo "  $file ($size, MD5: $checksum)" >> "$MANIFEST"
done

echo "  ✅ 备份清单生成完成"

# 清理旧备份
echo ""
echo "--- 清理旧备份 ---"
OLD_BACKUPS=$(find "$BACKUP_BASE_DIR/daily" -maxdepth 1 -type d -mtime +$RETENTION_DAYS)
if [ -n "$OLD_BACKUPS" ]; then
    echo "$OLD_BACKUPS" | while read -r old_backup; do
        echo "删除旧备份: $old_backup"
        rm -rf "$old_backup"
    done
    echo "  ✅ 清理完成"
else
    echo "  ✅ 无需清理"
fi

# 验证备份
echo ""
echo "--- 备份验证 ---"
ERROR_COUNT=0

# 检查关键文件是否存在
CRITICAL_FILES=(
    "$BACKUP_DIR/agora.db"
    "$BACKUP_DIR/configs.tar.gz"
    "$BACKUP_DIR/manifest.txt"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file 缺失"
        ERROR_COUNT=$((ERROR_COUNT + 1))
    fi
done

# 检查备份大小
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "备份大小: $BACKUP_SIZE"

if [ $ERROR_COUNT -eq 0 ]; then
    echo "备份验证: ✅ 全部通过"
    EXIT_CODE=0
else
    echo "备份验证: ❌ 发现 $ERROR_COUNT 个问题"
    EXIT_CODE=1
fi

# 发送备份完成通知
echo ""
echo "--- 备份完成通知 ---"
echo "备份位置: $BACKUP_DIR"
echo "备份大小: $BACKUP_SIZE"
echo "备份状态: $([ $EXIT_CODE -eq 0 ] && echo '成功' || echo '失败')"

# 这里可以集成通知服务，如邮件、Slack等
# curl -X POST "https://hooks.slack.com/..." \
#   -H "Content-Type: application/json" \
#   -d "{\"text\":\"Workspace备份完成: $([ $EXIT_CODE -eq 0 ] && echo '✅ 成功' || echo '❌ 失败')\"}"

exit $EXIT_CODE
