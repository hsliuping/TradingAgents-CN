#!/bin/bash
# Docker Entrypoint Script for TradingAgents-CN Backend
# 自动检测并执行数据库初始化（首次启动时）

# 注意：不使用 set -e，因为初始化失败时仍需要启动服务
set -u  # 只检查未定义变量

# 初始化标记文件路径
INIT_MARKER="/app/runtime/.config_imported"
RUNTIME_DIR="/app/runtime"

# 确保 runtime 目录存在
mkdir -p "$RUNTIME_DIR"

# 检查是否需要初始化
if [ ! -f "$INIT_MARKER" ]; then
    echo "=========================================="
    echo "🚀 首次启动检测到，开始初始化数据库..."
    echo "=========================================="
    echo ""
    
    # 等待 MongoDB 和 Redis 服务就绪
    echo "⏳ 等待数据库服务就绪..."
    
    # 等待 MongoDB（最多等待 60 秒）
    MAX_RETRIES=60
    RETRY_COUNT=0
    MONGO_READY=false
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if python -c "
import sys
try:
    from pymongo import MongoClient
    client = MongoClient('mongodb://admin:tradingagents123@mongodb:27017/tradingagents?authSource=admin', serverSelectionTimeoutMS=2000)
    client.server_info()
    sys.exit(0)
except:
    sys.exit(1)
" 2>/dev/null; then
            MONGO_READY=true
            break
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $((RETRY_COUNT % 10)) -eq 0 ]; then
            echo "   等待中... ($RETRY_COUNT/$MAX_RETRIES)"
        fi
        sleep 1
    done
    
    if [ "$MONGO_READY" = false ]; then
        echo "⚠️  警告: MongoDB 连接超时，但继续启动服务..."
        echo "   你可以稍后手动运行初始化脚本:"
        echo "   docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py"
    else
        echo "✅ MongoDB 连接成功"
        
        # 等待 Redis（可选，不阻塞）
        if python -c "
import sys
try:
    import redis
    r = redis.Redis(host='redis', port=6379, password='tradingagents123', socket_timeout=2)
    r.ping()
    sys.exit(0)
except:
    sys.exit(1)
" 2>/dev/null; then
            echo "✅ Redis 连接成功"
        else
            echo "⚠️  Redis 连接失败（可选服务）"
        fi
        
        echo ""
        echo "📦 开始导入配置数据并创建默认用户..."
        
        # 查找最新的配置文件
        CONFIG_DIR="/app/install"
        LATEST_CONFIG=$(find "$CONFIG_DIR" -name "database_export_config_*.json" -type f 2>/dev/null | sort -r | head -n 1)
        
        if [ -n "$LATEST_CONFIG" ] && [ -f "$LATEST_CONFIG" ]; then
            echo "   使用配置文件: $LATEST_CONFIG"
            
            # 执行初始化脚本（Docker 内运行，不使用 --host）
            # 使用 set +e 临时禁用错误退出，确保初始化失败时仍能启动服务
            set +e
            python scripts/import_config_and_create_user.py "$LATEST_CONFIG" 2>&1
            INIT_EXIT_CODE=$?
            set -u
            
            if [ $INIT_EXIT_CODE -eq 0 ]; then
                echo ""
                echo "✅ 数据库初始化完成！"
                
                # 创建标记文件
                echo "$(date -u +"%Y-%m-%d %H:%M:%S UTC")" > "$INIT_MARKER"
                echo "   标记文件已创建: $INIT_MARKER"
                echo ""
                echo "📋 默认登录信息:"
                echo "   用户名: admin"
                echo "   密码: admin123"
                echo "   ⚠️  请首次登录后立即修改密码！"
            else
                echo ""
                echo "⚠️  警告: 数据库初始化失败，但继续启动服务..."
                echo "   你可以稍后手动运行:"
                echo "   docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py"
            fi
        else
            echo "⚠️  警告: 未找到配置文件 (database_export_config_*.json)"
            echo "   跳过配置导入，仅创建默认用户..."
            
            # 尝试只创建用户
            set +e
            python scripts/import_config_and_create_user.py --create-user-only 2>&1
            USER_EXIT_CODE=$?
            set -u
            
            if [ $USER_EXIT_CODE -eq 0 ]; then
                echo "✅ 默认用户创建完成"
                echo "$(date -u +"%Y-%m-%d %H:%M:%S UTC")" > "$INIT_MARKER"
            else
                echo "⚠️  用户创建失败，但继续启动服务..."
            fi
        fi
        
        echo ""
        echo "=========================================="
    fi
else
    echo "ℹ️  数据库已初始化（标记文件存在: $INIT_MARKER）"
    echo "   跳过初始化步骤"
fi

echo ""
echo "🚀 启动 FastAPI 后端服务..."
echo ""

# 执行原始命令（CMD 或传入的参数）
exec "$@"
