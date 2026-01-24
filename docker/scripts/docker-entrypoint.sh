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
    # 注意：如果 MongoDB 容器已经运行，可以减少等待时间
    MAX_RETRIES=60
    RETRY_COUNT=0
    MONGO_READY=false
    
    # 🔍 先检查 MongoDB 容器是否存在（检查服务名，而不是容器名）
    echo "   检查 MongoDB 服务状态..."
    # 尝试通过服务名连接，如果失败再检查容器
    MONGO_CONTAINER=$(docker ps --filter "name=mongodb" --format "{{.Names}}" | head -n 1)
    
    # 🔍 快速检查：如果 MongoDB 容器已经运行一段时间，减少等待
    if [ -n "$MONGO_CONTAINER" ]; then
        CONTAINER_UPTIME=$(docker inspect --format='{{.State.StartedAt}}' "$MONGO_CONTAINER" 2>/dev/null)
        if [ -n "$CONTAINER_UPTIME" ]; then
            # 如果容器已运行超过 30 秒，减少最大重试次数
            CURRENT_TIME=$(date +%s)
            START_TIME=$(date -d "$CONTAINER_UPTIME" +%s 2>/dev/null || echo "0")
            if [ "$START_TIME" != "0" ] && [ $((CURRENT_TIME - START_TIME)) -gt 30 ]; then
                echo "   MongoDB 容器已运行超过 30 秒，使用快速模式（最多等待 20 秒）"
                MAX_RETRIES=20
            fi
        fi
    fi
    if [ -z "$MONGO_CONTAINER" ]; then
        echo "   ⚠️  警告: 未找到 MongoDB 容器（名称包含 mongodb）"
        echo "   提示: 将尝试通过服务名 'mongodb' 连接"
    else
        echo "   ✅ 找到 MongoDB 容器: $MONGO_CONTAINER"
    fi
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        # 尝试连接 MongoDB（增加超时时间到 5 秒）
        # 使用更详细的错误输出以便诊断
        MONGO_TEST_OUTPUT=$(python -c "
import sys
import traceback
try:
    from pymongo import MongoClient
    print('正在连接 MongoDB...', file=sys.stderr)
    client = MongoClient('mongodb://admin:tradingagents123@mongodb:27017/tradingagents?authSource=admin', serverSelectionTimeoutMS=5000)
    info = client.server_info()
    print('连接成功，MongoDB 版本: ' + info.get('version', 'unknown'), file=sys.stderr)
    sys.exit(0)
except Exception as e:
    print('连接失败: ' + str(e), file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
" 2>&1)
        
        MONGO_EXIT_CODE=$?
        if [ $MONGO_EXIT_CODE -eq 0 ]; then
            MONGO_READY=true
            # 显示成功信息
            echo "$MONGO_TEST_OUTPUT" | grep -v "^$" | head -n 3
            break
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $((RETRY_COUNT % 10)) -eq 0 ]; then
            echo "   等待中... ($RETRY_COUNT/$MAX_RETRIES)"
            # 每 10 次重试显示一次错误信息
            if [ -n "$MONGO_TEST_OUTPUT" ]; then
                echo "   最近错误: $(echo "$MONGO_TEST_OUTPUT" | tail -n 1 | cut -c 1-150)"
            fi
        fi
        sleep 1
    done
    
    if [ "$MONGO_READY" = false ]; then
        echo ""
        echo "⚠️  警告: MongoDB 连接超时（已等待 60 秒）"
        echo ""
        echo "可能的原因："
        echo "1. MongoDB 容器未正常启动"
        echo "2. 网络连接问题（容器名解析失败）"
        echo "3. MongoDB 数据卷损坏"
        echo ""
        echo "诊断步骤："
        echo "1. 检查 MongoDB 容器: docker ps -a | grep mongodb"
        echo "2. 查看 MongoDB 日志: docker logs tradingagents-mongodb"
        echo "3. 检查网络: docker network inspect tradingagents-network"
        echo "4. 运行诊断脚本: docker exec tradingagents-backend bash -c 'if [ -f /app/docker/scripts/diagnose_mongodb.sh ]; then bash /app/docker/scripts/diagnose_mongodb.sh; fi'"
        echo ""
        echo "解决方案："
        echo "1. 重启 MongoDB: docker restart tradingagents-mongodb"
        echo "2. 删除数据卷重建（会丢失数据）:"
        echo "   docker-compose down -v"
        echo "   docker volume rm tradingagents_mongodb_data"
        echo "   docker-compose up -d mongodb"
        echo ""
        echo "继续启动服务，你可以稍后手动运行初始化脚本:"
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
