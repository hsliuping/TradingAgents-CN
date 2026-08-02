#!/bin/bash
# Docker Entrypoint Script for TradingAgents-CN Backend
# 自动检测并执行数据库初始化（首次启动时）
# 🔐 安全：以 root 启动处理挂载卷权限，然后用 gosu 切换到非 root 用户运行应用

# 注意：不使用 set -e，因为初始化失败时仍需要启动服务
set -u  # 只检查未定义变量

# 初始化标记文件路径
INIT_MARKER="/app/runtime/.config_imported"
RUNTIME_DIR="/app/runtime"
LOG_FILE="/app/logs/docker-entrypoint.log"

# 🔐 安全：以 root 身份确保挂载卷目录权限正确，然后切换到 appuser
# 宿主机挂载的 ./logs ./data ./runtime 目录可能由 root 拥有，需要 chown 给 appuser
APP_USER="${APP_USER:-appuser}"
APP_UID="${APP_UID:-1000}"
APP_GID="${APP_GID:-1000}"

if [ "$(id -u)" = "0" ]; then
    # 确保 appuser 用户和组存在（与 Dockerfile 中一致）
    if ! getent group "$APP_GID" >/dev/null 2>&1; then
        groupadd --system --gid "$APP_GID" "$APP_USER" 2>/dev/null || true
    fi
    if ! id -u "$APP_USER" >/dev/null 2>&1; then
        useradd --system --uid "$APP_UID" --gid "$APP_GID" \
            --home-dir /app --shell /usr/sbin/nologin "$APP_USER" 2>/dev/null || true
    fi

    # 确保挂载卷目录存在并归属 appuser
    mkdir -p "$RUNTIME_DIR" /app/logs /app/data 2>/dev/null || true
    chown -R "$APP_USER":"$APP_GID" /app/logs /app/data /app/runtime 2>/dev/null || true
fi

# 确保目录存在（非 root 也能创建，因为已 chown）
mkdir -p "$RUNTIME_DIR" 2>/dev/null || true
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

# 日志函数：同时输出到 stdout 和日志文件
log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" | tee -a "$LOG_FILE"
}

# 错误日志函数：输出到 stderr 和日志文件
log_error() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] ERROR: $message" | tee -a "$LOG_FILE" >&2
}

check_admin_user_exists() {
    python -c "
import os
import sys

from pymongo import MongoClient

mongo_host = os.getenv('MONGODB_HOST', 'mongodb')
mongo_port = os.getenv('MONGODB_PORT', '27017')
mongo_username = os.getenv('MONGODB_USERNAME', 'admin')
# 🔐 安全：移除硬编码弱密码默认值，必须通过环境变量提供
mongo_password = os.getenv('MONGODB_PASSWORD', '')
mongo_database = os.getenv('MONGODB_DATABASE', 'tradingagents')
mongo_auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

if not mongo_password:
    print('错误：MONGODB_PASSWORD 环境变量未设置', file=sys.stderr)
    sys.exit(2)

connection_string = f'mongodb://{mongo_username}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_database}?authSource={mongo_auth_source}'
client = MongoClient(connection_string, serverSelectionTimeoutMS=3000)
user = client[mongo_database]['users'].find_one({'username': 'admin'}, {'_id': 1})
client.close()
sys.exit(0 if user else 1)
" 2>&1
}

SHOULD_INIT=true
INIT_REASON="未找到初始化标记文件"

if [ -f "$INIT_MARKER" ]; then
    ADMIN_CHECK_OUTPUT=$(check_admin_user_exists)
    ADMIN_CHECK_EXIT_CODE=$?

    if [ $ADMIN_CHECK_EXIT_CODE -eq 0 ]; then
        SHOULD_INIT=false
    else
        log "⚠️  初始化标记已存在，但数据库中未检测到 admin 用户"
        if [ -n "$ADMIN_CHECK_OUTPUT" ]; then
            echo "$ADMIN_CHECK_OUTPUT" | tee -a "$LOG_FILE"
        fi
        rm -f "$INIT_MARKER"
        INIT_REASON="检测到陈旧初始化标记，已移除并重新执行初始化"
    fi
fi

# 检查是否需要初始化
if [ "$SHOULD_INIT" = true ]; then
    log "=========================================="
    log "🚀 首次启动检测到，开始初始化数据库..."
    log "=========================================="
    log ""
    log "📝 日志文件位置: $LOG_FILE"
    log "📝 初始化原因: $INIT_REASON"
    log ""
    
    # 等待 MongoDB 和 Redis 服务就绪
    log "⏳ 等待数据库服务就绪..."
    
    # 等待 MongoDB（最多等待 60 秒）
    MAX_RETRIES=60
    RETRY_COUNT=0
    MONGO_READY=false

    # 检查网络连接性
    log "   检查 MongoDB 服务网络连接性..."
    if command -v getent >/dev/null 2>&1; then
        if getent hosts mongodb >/dev/null 2>&1; then
            log "   ✅ 可以通过 DNS 解析 'mongodb' 主机名"
        else
            log "   ⚠️  无法通过 DNS 解析 'mongodb' 主机名，将尝试直接连接"
        fi
    fi
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        # 尝试连接 MongoDB（增加超时时间到 5 秒）
        # 使用更详细的错误输出以便诊断
        # 注意：MongoDB 官方镜像通过 MONGO_INITDB_ROOT_USERNAME 和 MONGO_INITDB_ROOT_PASSWORD 环境变量
        # 会在首次启动时自动创建 root 用户，所以这里直接尝试有认证连接
        MONGO_TEST_OUTPUT=$(python -c "
import sys
import traceback
try:
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure, ConfigurationError

    print('正在连接 MongoDB...', file=sys.stderr)

    # 尝试多种连接方式
    # 方式1: 使用 Docker Compose 服务名 'mongodb'
    # 方式2: 如果失败，尝试使用环境变量中的主机名
    import os
    mongo_host = os.getenv('MONGODB_HOST', 'mongodb')
    mongo_port = os.getenv('MONGODB_PORT', '27017')
    mongo_username = os.getenv('MONGODB_USERNAME', 'admin')
    # 🔐 安全：移除硬编码弱密码默认值，必须通过环境变量提供
    mongo_password = os.getenv('MONGODB_PASSWORD', '')
    mongo_database = os.getenv('MONGODB_DATABASE', 'tradingagents')
    mongo_auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

    if not mongo_password:
        print('错误：MONGODB_PASSWORD 环境变量未设置', file=sys.stderr)
        sys.exit(1)
    
    connection_string = f'mongodb://{mongo_username}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_database}?authSource={mongo_auth_source}'
    print(f'连接字符串: mongodb://{mongo_username}:***@{mongo_host}:{mongo_port}/{mongo_database}?authSource={mongo_auth_source}', file=sys.stderr)
    
    # 尝试有认证连接（MongoDB 官方镜像会自动创建 root 用户）
    client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
    info = client.server_info()
    print('连接成功，MongoDB 版本: ' + info.get('version', 'unknown'), file=sys.stderr)
    
    # 验证认证系统是否已初始化（检查 admin 用户是否存在）
    try:
        admin_db = client.admin
        users = admin_db.command('usersInfo', 'admin')
        if users.get('users'):
            print('MongoDB 认证系统已初始化', file=sys.stderr)
        else:
            print('警告: MongoDB admin 用户不存在，可能需要初始化', file=sys.stderr)
    except Exception as e:
        print('检查用户时出错: ' + str(e), file=sys.stderr)
    
    client.close()
    sys.exit(0)
except OperationFailure as e:
    # 认证失败，可能是用户不存在或密码错误
    error_msg = str(e)
    if 'Authentication failed' in error_msg or 'auth failed' in error_msg.lower():
        print('认证失败: ' + error_msg, file=sys.stderr)
        print('提示: MongoDB 可能未初始化认证系统，请检查 MONGO_INITDB_ROOT_USERNAME 和 MONGO_INITDB_ROOT_PASSWORD 环境变量', file=sys.stderr)
    else:
        print('操作失败: ' + error_msg, file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print('连接失败: ' + str(e), file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
" 2>&1)
        
        MONGO_EXIT_CODE=$?
        if [ $MONGO_EXIT_CODE -eq 0 ]; then
            MONGO_READY=true
            # 显示成功信息并记录到日志
            SUCCESS_MSG=$(echo "$MONGO_TEST_OUTPUT" | grep -v "^$" | head -n 3)
            echo "$SUCCESS_MSG"
            echo "$SUCCESS_MSG" >> "$LOG_FILE"
            break
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $((RETRY_COUNT % 10)) -eq 0 ]; then
            log "   等待中... ($RETRY_COUNT/$MAX_RETRIES)"
            # 每 10 次重试显示一次错误信息
            if [ -n "$MONGO_TEST_OUTPUT" ]; then
                ERROR_MSG="   最近错误: $(echo "$MONGO_TEST_OUTPUT" | tail -n 1 | cut -c 1-150)"
                log_error "$ERROR_MSG"
            fi
        fi
        sleep 1
    done
    
    if [ "$MONGO_READY" = false ]; then
        log ""
        log_error "⚠️  警告: MongoDB 连接超时（已等待 60 秒）"
        log ""
        log "可能的原因："
        log "1. MongoDB 容器未正常启动或未加入同一网络"
        log "2. DNS 解析问题（容器内无法解析 'mongodb' 主机名）"
        log "3. Docker Compose 网络配置问题"
        log "4. MongoDB 容器启动顺序问题"
        log ""
        log "诊断步骤："
        log "1. 检查 MongoDB 容器状态:"
        log "   docker ps -a | grep -i mongo"
        log "   docker logs tradingagents-mongodb-propro"
        log ""
        log "2. 检查网络配置:"
        log "   docker network inspect tradingagents-network"
        log "   docker network ls"
        log ""
        log "3. 检查容器网络连接（在宿主机执行）:"
        log "   docker exec tradingagents-backend-pro ping -c 3 mongodb"
        log "   docker exec tradingagents-backend-pro getent hosts mongodb"
        log ""
        log "4. 检查环境变量:"
        log "   docker exec tradingagents-backend-pro env | grep MONGODB"
        log ""
        log "5. 查看完整日志:"
        log "   docker logs tradingagents-backend-pro"
        log "   docker exec tradingagents-backend-pro cat $LOG_FILE"
        log ""
        log "解决方案："
        log "1. 确保使用正确的 docker-compose 文件启动:"
        log "   cd docker && docker-compose -f docker-compose.compiled.yml up -d mongodb"
        log ""
        log "2. 检查 docker-compose.yml 中的网络配置:"
        log "   - 确保所有服务都在 'tradingagents-network' 网络中"
        log "   - 确保 MongoDB 服务名是 'mongodb'"
        log ""
        log "3. 重启所有服务:"
        log "   cd docker && docker-compose -f docker-compose.compiled.yml down"
        log "   cd docker && docker-compose -f docker-compose.compiled.yml up -d"
        log ""
        log "4. 如果问题持续，尝试手动连接测试:"
        log "   docker exec tradingagents-backend-pro python -c \"from pymongo import MongoClient; import os; pwd=os.getenv('MONGODB_PASSWORD'); client = MongoClient(f'mongodb://admin:{pwd}@mongodb:27017/tradingagents?authSource=admin', serverSelectionTimeoutMS=5000); print(client.server_info())\""
        log ""
        log "继续启动服务，你可以稍后手动运行初始化脚本:"
        log "   docker exec -it tradingagents-backend-pro python scripts/import_config_and_create_user.py"
    else
        log "✅ MongoDB 连接成功"
        
        # 等待 Redis（可选，不阻塞）
        if python -c "
import sys
import os
try:
    import redis
    redis_pwd = os.getenv('REDIS_PASSWORD', '')
    r = redis.Redis(host='redis', port=6379, password=redis_pwd, socket_timeout=2)
    r.ping()
    sys.exit(0)
except:
    sys.exit(1)
" 2>/dev/null; then
            log "✅ Redis 连接成功"
        else
            log "⚠️  Redis 连接失败（可选服务）"
        fi
        
        log ""
        log "📦 开始导入配置数据并创建默认用户..."
        
        # 查找最新的配置文件
        CONFIG_DIR="/app/install"
        LATEST_CONFIG=$(find "$CONFIG_DIR" -name "database_export_config_*.json" -type f 2>/dev/null | sort -r | head -n 1)
        
        if [ -n "$LATEST_CONFIG" ] && [ -f "$LATEST_CONFIG" ]; then
            log "   使用配置文件: $LATEST_CONFIG"
            
            # 执行初始化脚本（Docker 内运行，不使用 --host）
            # 使用 set +e 临时禁用错误退出，确保初始化失败时仍能启动服务
            # 同时输出到 stdout 和日志文件
            set +e
            python scripts/import_config_and_create_user.py "$LATEST_CONFIG" 2>&1 | tee -a "$LOG_FILE"
            INIT_EXIT_CODE=${PIPESTATUS[0]}
            set -u
            
            if [ $INIT_EXIT_CODE -eq 0 ]; then
                log ""
                log "✅ 数据库初始化完成！"
                
                # 创建标记文件
                echo "$(date -u +"%Y-%m-%d %H:%M:%S UTC")" > "$INIT_MARKER"
                log "   标记文件已创建: $INIT_MARKER"
                log ""
                log "📋 默认登录信息:"
                log "   用户名: admin"
                log "   密码: 由 ADMIN_DEFAULT_PASSWORD 环境变量指定"
                log "   ⚠️  请首次登录后立即修改密码！"
            else
                log ""
                log_error "⚠️  警告: 数据库初始化失败，但继续启动服务..."
                log "   你可以稍后手动运行:"
                log "   docker exec -it tradingagents-backend-pro python scripts/import_config_and_create_user.py"
                log "   查看详细日志: cat $LOG_FILE"
            fi
        else
            log "⚠️  警告: 未找到配置文件 (database_export_config_*.json)"
            log "   跳过配置导入，仅创建默认用户..."
            
            # 尝试只创建用户
            set +e
            python scripts/import_config_and_create_user.py --create-user-only 2>&1 | tee -a "$LOG_FILE"
            USER_EXIT_CODE=${PIPESTATUS[0]}
            set -u
            
            if [ $USER_EXIT_CODE -eq 0 ]; then
                log "✅ 默认用户创建完成"
                echo "$(date -u +"%Y-%m-%d %H:%M:%S UTC")" > "$INIT_MARKER"
            else
                log_error "⚠️  用户创建失败，但继续启动服务..."
                log "   查看详细日志: cat $LOG_FILE"
            fi
        fi
        
        log ""
        log "=========================================="
    fi
else
    log "ℹ️  数据库已初始化（标记文件存在: $INIT_MARKER）"
    log "   跳过初始化步骤"
fi

log ""
log "🚀 启动 FastAPI 后端服务..."
log ""

# 🔐 安全：以非 root 用户运行应用
# 如果当前是 root，用 gosu 切换到 appuser；否则直接执行
if [ "$(id -u)" = "0" ] && command -v gosu >/dev/null 2>&1; then
    log "🔐 切换到非 root 用户运行: $APP_USER (UID=$APP_UID)"
    exec gosu "$APP_USER" "$@"
else
    exec "$@"
fi
