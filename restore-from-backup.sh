#!/bin/bash
# 从备份恢复脚本
# 版本: v1.0
# 创建日期: 2026-05-24
# 用途: 从备份恢复数据

set -e  # 遇到错误立即退出

# 配置
WORKSPACE="/Users/xiamingxing/Workspace"
BACKUP_BASE_DIR="${WORKSPACE}/backups"

# 检查参数
if [ $# -lt 1 ]; then
    echo "用法: $0 <备份日期> [选项]"
    echo ""
    echo "备份日期格式: YYYYMMDD (例如: 20260524)"
    echo ""
    echo "选项:"
    echo "  --dry-run     只显示将要执行的操作，不实际恢复"
    echo "  --services    指定要恢复的服务 (逗号分隔)"
    echo "  --skip-prompt 跳过确认提示"
    echo ""
    echo "示例:"
    echo "  $0 20260524"
    echo "  $0 20260524 --dry-run"
    echo "  $0 20260524 --services agora,minerva"
    exit 1
fi

BACKUP_DATE=$1
BACKUP_DIR="${BACKUP_BASE_DIR}/daily/${BACKUP_DATE}"

# 检查备份是否存在
if [ ! -d "$BACKUP_DIR" ]; then
    echo "错误: 备份目录不存在: $BACKUP_DIR"
    echo ""
    echo "可用的备份:"
    find "$BACKUP_BASE_DIR/daily" -maxdepth 1 -type d | sort -r | head -5
    exit 1
fi

# 解析选项
DRY_RUN=false
SERVICES="all"
SKIP_PROMPT=false

shift
while [ $# -gt 0 ]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --services)
            SERVICES="$2"
            shift 2
            ;;
        --skip-prompt)
            SKIP_PROMPT=true
            shift
            ;;
        *)
            echo "未知选项: $1"
            exit 1
            ;;
    esac
done

# 显示备份信息
echo "=== 从备份恢复 ==="
echo "备份日期: $BACKUP_DATE"
echo "备份目录: $BACKUP_DIR"
echo ""

# 检查备份清单
if [ -f "$BACKUP_DIR/manifest.txt" ]; then
    echo "备份清单:"
    cat "$BACKUP_DIR/manifest.txt"
    echo ""
else
    echo "⚠️  备份清单不存在"
    echo ""
fi

# 显示将要恢复的服务
echo "将要恢复的服务:"
case $SERVICES in
    all)
        echo "  - 所有服务"
        ;;
    *)
        IFS=',' read -ra SERVICE_ARRAY <<< "$SERVICES"
        for service in "${SERVICE_ARRAY[@]}"; do
            echo "  - $service"
        done
        ;;
esac
echo ""

# 恢复函数
restore_file() {
    local source="$1"
    local dest="$2"
    
    if [ -f "$source" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "  [DRY-RUN] 恢复文件: $source → $dest"
        else
            echo "  恢复文件: $source → $dest"
            cp "$source" "$dest"
        fi
        return 0
    else
        echo "  ⚠️  源文件不存在: $source"
        return 1
    fi
}

restore_dir() {
    local source="$1"
    local dest="$2"
    
    if [ -d "$source" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "  [DRY-RUN] 恢复目录: $source → $dest"
        else
            echo "  恢复目录: $source → $dest"
            rsync -av "$source/" "$dest/" --delete
        fi
        return 0
    else
        echo "  ⚠️  源目录不存在: $source"
        return 1
    fi
}

# 恢复配置文件
restore_configs() {
    echo "--- 恢复配置文件 ---"
    
    local config_tar="$BACKUP_DIR/configs.tar.gz"
    if [ -f "$config_tar" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "  [DRY-RUN] 解压配置文件"
        else
            echo "  解压配置文件"
            tar -xzf "$config_tar" -C "$WORKSPACE"
        fi
        echo "  ✅ 配置文件恢复完成"
    else
        echo "  ⚠️  配置文件备份不存在"
        return 1
    fi
}

# 恢复数据库
restore_databases() {
    echo "--- 恢复数据库 ---"
    
    local db_restored=false
    
    # 恢复agora.db
    if [ "$SERVICES" = "all" ] || [[ ",$SERVICES," == *,agora,* ]]; then
        restore_file "$BACKUP_DIR/agora.db" "$WORKSPACE/projects/kairon/packages/agora/agora.db"
        db_restored=true
    fi
    
    # 恢复agentmesh.db
    if [ "$SERVICES" = "all" ] || [[ ",$SERVICES," == *,agentmesh,* ]]; then
        restore_file "$BACKUP_DIR/agentmesh.db" "$WORKSPACE/projects/agentmesh/data/gateway.db"
        db_restored=true
    fi
    
    if [ "$db_restored" = true ]; then
        echo "  ✅ 数据库恢复完成"
    fi
}

# 恢复向量数据库
restore_vector_db() {
    echo "--- 恢复向量数据库 ---"
    
    if [ "$SERVICES" = "all" ] || [[ ",$SERVICES," == *,minerva,* ]]; then
        restore_dir "$BACKUP_DIR/lancedb" "$WORKSPACE/projects/kairon/packages/minerva/data/lancedb"
        echo "  ✅ 向量数据库恢复完成"
    else
        echo "  跳过向量数据库恢复"
    fi
}

# 恢复用户数据
restore_user_data() {
    echo "--- 恢复用户数据 ---"
    
    # 恢复Forge数据
    if [ -d "$BACKUP_DIR/forge-data" ]; then
        restore_dir "$BACKUP_DIR/forge-data" "$WORKSPACE/projects/kairon/packages/forge"
    fi
    
    echo "  ✅ 用户数据恢复完成"
}

# 重启服务
restart_services() {
    echo "--- 重启服务 ---"
    
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY-RUN] 重启所有服务"
        echo "  [DRY-RUN] docker compose restart"
        return 0
    fi
    
    cd "$WORKSPACE"
    
    # 停止现有服务
    echo "  停止现有服务..."
    docker compose down 2>/dev/null || true
    
    # 启动服务
    echo "  启动服务..."
    docker compose up -d
    
    # 等待服务启动
    echo "  等待服务启动..."
    sleep 10
    
    # 检查服务状态
    echo "  检查服务状态..."
    docker compose ps
    
    echo "  ✅ 服务重启完成"
}

# 执行恢复
ERROR_COUNT=0

case $SERVICES in
    all)
        restore_configs || ERROR_COUNT=$((ERROR_COUNT + 1))
        restore_databases || ERROR_COUNT=$((ERROR_COUNT + 1))
        restore_vector_db || ERROR_COUNT=$((ERROR_COUNT + 1))
        restore_user_data || ERROR_COUNT=$((ERROR_COUNT + 1))
        ;;
    *)
        IFS=',' read -ra SERVICE_ARRAY <<< "$SERVICES"
        for service in "${SERVICE_ARRAY[@]}"; do
            case $service in
                agora|minerva|agentmesh)
                    restore_databases || ERROR_COUNT=$((ERROR_COUNT + 1))
                    ;;
                configs)
                    restore_configs || ERROR_COUNT=$((ERROR_COUNT + 1))
                    ;;
                vector)
                    restore_vector_db || ERROR_COUNT=$((ERROR_COUNT + 1))
                    ;;
                user)
                    restore_user_data || ERROR_COUNT=$((ERROR_COUNT + 1))
                    ;;
                *)
                    echo "  ⚠️  未知服务: $service"
                    ERROR_COUNT=$((ERROR_COUNT + 1))
                    ;;
            esac
        done
        ;;
esac

# 确认操作
if [ "$DRY_RUN" = false ] && [ $ERROR_COUNT -eq 0 ]; then
    if [ "$SKIP_PROMPT" = false ]; then
        echo ""
        echo "⚠️  即将重启服务，确保："
        echo "  1. 所有正在进行的任务已完成"
        echo "  2. 数据已正确备份"
        echo "  3. 团队成员已知晓此次恢复"
        echo ""
        read -p "确认重启服务？(yes/no): " confirm
        
        if [ "$confirm" != "yes" ]; then
            echo "恢复操作已取消"
            exit 0
        fi
    fi
    
    restart_services
fi

# 恢复结果
echo ""
echo "=== 恢复完成 ==="
echo "备份日期: $BACKUP_DATE"
echo "恢复状态: $([ $ERROR_COUNT -eq 0 ] && echo '✅ 成功' || echo '❌ 失败 (发现 ' $ERROR_COUNT ' 个问题)')"

if [ $ERROR_COUNT -eq 0 ]; then
    echo ""
    echo "后续操作:"
    echo "  1. 验证服务状态: cd $WORKSPACE && docker compose ps"
    echo "  2. 检查服务日志: docker compose logs"
    echo "  3. 测试关键功能: workspace research test"
    echo "  4. 监控系统状态: curl localhost:7430/health"
    exit 0
else
    echo ""
    echo "恢复过程中发现问题，请检查日志"
    exit 1
fi
