#!/bin/bash
# TradingAgents-CN Pro 单容器启动脚本
#
# 用法：
#   bash run.sh                # 普通版（使用 .env.docker）
#   bash run.sh --jdyun        # 京东云版（使用 .env.docker.jdyun）
#   bash run.sh --dev          # 开发模式：挂载本地代码，改代码后重启后端即可生效
#   bash run.sh --jdyun --dev  # 京东云版 + 开发模式
#   bash run.sh --build        # 先构建镜像再启动
#   bash run.sh --stop         # 停止并删除容器
#   bash run.sh --logs         # 查看容器日志
#   bash run.sh --shell        # 进入容器 shell
#   bash run.sh --status       # 查看容器状态
#   bash run.sh --restart-be   # 重启后端进程（开发模式下改完代码用）
#   bash run.sh --clean        # 清理所有数据卷（危险！）

set -eu

IMAGE_NAME="${IMAGE_NAME:-tradingagents-cn-pro}"
IMAGE_TAG="${IMAGE_TAG:-3.0.0}"
CONTAINER_NAME="${CONTAINER_NAME:-tradingagents}"

# 京东云模式标记（--jdyun 参数设置）
# 京东云版镜像 tag 为 3.0.0-jdyun，数据卷为 ta-data
# 详见 docs/jdyun-branch-guide.md
JDYUN_MODE_FLAG=false
DEV_MODE=false

# 数据卷名
VOLUME_MONGO="ta-mongo-data"
VOLUME_REDIS="ta-redis-data"
VOLUME_RUNTIME="ta-runtime"
VOLUME_LOGS="ta-logs"
VOLUME_QDRANT="ta-qdrant"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ------------------------------------------------------------------------------
# 加载配置文件
# ------------------------------------------------------------------------------
# 优先级：
#   1. --jdyun 参数 → 加载 .env.docker.jdyun
#   2. 默认 → 加载 .env.docker
#   3. 回退 → 加载 .env
# 命令行 export 的环境变量优先级最高，不会被文件覆盖
# ------------------------------------------------------------------------------

load_env_file() {
    local env_file=""

    if [ "$JDYUN_MODE_FLAG" = true ]; then
        # 京东云版
        if [ -f "$SCRIPT_DIR/.env.docker.jdyun" ]; then
            env_file="$SCRIPT_DIR/.env.docker.jdyun"
        else
            echo "❌ 京东云版配置文件不存在: .env.docker.jdyun"
            exit 1
        fi
    else
        # 普通版
        if [ -f "$SCRIPT_DIR/.env.docker" ]; then
            env_file="$SCRIPT_DIR/.env.docker"
        elif [ -f "$SCRIPT_DIR/.env" ]; then
            env_file="$SCRIPT_DIR/.env"
        fi
    fi

    if [ -n "$env_file" ]; then
        echo "📄 加载配置: $env_file"
        while IFS='=' read -r key value; do
            [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)
            # 只设置尚未定义的环境变量（export 优先级更高）
            if [ -z "${!key:-}" ]; then
                export "$key=$value"
            fi
        done < "$env_file"
    fi
}

check_required_env() {
    if [ -z "${MONGODB_PASSWORD:-}" ]; then
        echo "❌ 错误：MONGODB_PASSWORD 未设置"
        echo ""
        echo "   请编辑 .env.docker 文件，设置 MONGODB_PASSWORD"
        exit 1
    fi

    # 京东云版额外检查
    if [ "${JDYUN_MODE:-false}" = "true" ]; then
        if [ -z "${OPENAI_API_KEY:-}" ]; then
            echo "❌ 错误：京东云模式下 OPENAI_API_KEY 未设置"
            echo "   请在 .env.docker.jdyun 中填写京东云提供的 API Key"
            exit 1
        fi
    fi
}

# ------------------------------------------------------------------------------
# 参数解析
# ------------------------------------------------------------------------------
ACTION="start"
while [ $# -gt 0 ]; do
    case "$1" in
        --jdyun) JDYUN_MODE_FLAG=true; shift ;;
        --dev) DEV_MODE=true; shift ;;
        --build) ACTION="build"; shift ;;
        --stop) ACTION="stop"; shift ;;
        --logs) ACTION="logs"; shift ;;
        --shell) ACTION="shell"; shift ;;
        --status) ACTION="status"; shift ;;
        --restart-be) ACTION="restart-be"; shift ;;
        --clean) ACTION="clean"; shift ;;
        --help|-h)
            cat <<EOF
用法: bash run.sh [选项]

选项:
  --jdyun         京东云合作版模式
  --dev           开发模式：挂载本地代码目录，改代码后用 --restart-be 重启后端
  --build         先构建镜像再启动
  --stop          停止并删除容器
  --logs          查看容器日志
  --shell         进入容器 shell
  --status        查看容器状态
  --restart-be    重启容器内的后端进程（开发模式下改完代码用）
  --clean         清理所有数据卷（危险！）
  --help          显示此帮助

示例:
  bash run.sh                          # 普通版启动
  bash run.sh --jdyun                  # 京东云版启动
  bash run.sh --jdyun --dev            # 京东云版 + 开发模式
  bash run.sh --restart-be             # 改完代码后重启后端（秒级生效）
  bash run.sh --logs                   # 查看日志
  bash run.sh --stop                   # 停止容器
EOF
            exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# 加载配置文件
load_env_file

# 京东云版使用 -jdyun 后缀的镜像 tag 和 ta-data 数据卷
if [ "$JDYUN_MODE_FLAG" = true ]; then
    IMAGE_TAG="${IMAGE_TAG}-jdyun"
fi

# ------------------------------------------------------------------------------
# 镜像存在性检查
# ------------------------------------------------------------------------------
check_image() {
    if ! docker image inspect "${IMAGE_NAME}:${IMAGE_TAG}" &> /dev/null; then
        echo "❌ 镜像 ${IMAGE_NAME}:${IMAGE_TAG} 不存在"
        echo "   请先执行: bash build.sh"
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# 各动作
# ------------------------------------------------------------------------------
action_build() {
    check_required_env
    bash "$SCRIPT_DIR/build.sh" "$IMAGE_TAG"
    action_start
}

action_start() {
    check_required_env
    check_image

    # 京东云版使用独立的 MongoDB 数据卷 ta-data（7.0 格式，已迁移）
    # 与普通版的 ta-mongo-data 完全隔离，其他卷（redis/runtime/logs）共享
    # 详见 docs/jdyun-branch-guide.md
    if [ "${JDYUN_MODE:-false}" = "true" ]; then
        VOLUME_MONGO="ta-data"
    fi

    # 停止已存在的同名容器
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "🛑 停止已存在的容器: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME" &> /dev/null || true
        docker rm "$CONTAINER_NAME" &> /dev/null || true
    fi

    local MODE_LABEL="普通版"
    if [ "${JDYUN_MODE:-false}" = "true" ]; then
        MODE_LABEL="京东云版"
    fi
    if [ "$DEV_MODE" = true ]; then
        MODE_LABEL="$MODE_LABEL + 开发模式"
    fi

    echo "=========================================="
    echo "  🚀 启动单容器（$MODE_LABEL）"
    echo "=========================================="
    echo "  镜像:     ${IMAGE_NAME}:${IMAGE_TAG}"
    echo "  容器:     $CONTAINER_NAME"
    echo "  端口:     http://localhost:${HOST_PORT:-8082}"
    if [ "$DEV_MODE" = true ]; then
        echo "  代码挂载: $PROJECT_ROOT → /app"
    fi
    echo "=========================================="
    echo ""

    # 基础参数（两种模式都有）
    local RUN_ARGS=(
        -d
        --name "$CONTAINER_NAME"
        --hostname tradingagents
        --restart unless-stopped
        -p "${HOST_PORT:-8082}:8082"
        -p "${MONGO_HOST_PORT:-27019}:27017"
        -v "${VOLUME_MONGO}:/data/db"
        -v "${VOLUME_REDIS}:/var/lib/redis"
        -v "${VOLUME_RUNTIME}:/app/runtime"
        -v "${VOLUME_LOGS}:/app/logs"
        -v "${VOLUME_QDRANT}:/app/data"
        -e MONGODB_PASSWORD="$MONGODB_PASSWORD"
        -e TZ="${TZ:-Asia/Shanghai}"
    )

    # 开发模式：挂载本地代码目录，改代码后用 --restart-be 重启后端即可生效
    if [ "$DEV_MODE" = true ]; then
        RUN_ARGS+=(
            -v "$PROJECT_ROOT/app:/app/app"
            -v "$PROJECT_ROOT/core:/app/core"
            -v "$PROJECT_ROOT/tradingagents:/app/tradingagents"
            -v "$PROJECT_ROOT/config:/app/config"
            -v "$PROJECT_ROOT/scripts:/app/scripts"
            -v "$PROJECT_ROOT/migrations:/app/migrations"
            -v "$PROJECT_ROOT/VERSION:/app/VERSION"
        )
        # 开发模式也挂载前端编译产物（需先在本地 npm run build）
        if [ -d "$PROJECT_ROOT/frontend/dist" ]; then
            RUN_ARGS+=(
                -v "$PROJECT_ROOT/frontend/dist:/app/frontend/dist"
            )
        fi
    fi

    # 京东云版额外参数
    if [ "${JDYUN_MODE:-false}" = "true" ]; then
        RUN_ARGS+=(
            -e JDYUN_MODE=true
            -e OPENAI_API_BASE="${OPENAI_API_BASE:-}"
            -e OPENAI_API_KEY="${OPENAI_API_KEY:-}"
            -e OPENAI_MODEL="${OPENAI_MODEL:-GLM-5.1}"
            -e EMBEDDING_MODEL="${EMBEDDING_MODEL:-Qwen3-Embedding-8B}"
            -e EMBEDDING_API_BASE="${EMBEDDING_API_BASE:-https://modelservice.jdcloud.com/v1}"
            -e EMBEDDING_API_KEY="${EMBEDDING_API_KEY:-}"
            -e TUSHARE_TOKEN="${TUSHARE_TOKEN:-}"
            -e SEARXNG_INSTANCES="${SEARXNG_INSTANCES:-http://127.0.0.1:8888}"
            -e JDYUN_BASIC_AUTH_USERS="${JDYUN_BASIC_AUTH_USERS:-}"
            -e JDYUN_GATEWAY_IPS="${JDYUN_GATEWAY_IPS:-}"
            -e JDYUN_LLM_MAX_RETRIES="${JDYUN_LLM_MAX_RETRIES:-8}"
            -e JDYUN_LLM_MAX_RPM="${JDYUN_LLM_MAX_RPM:-30}"
            -e JDYUN_BATCH_MAX_CONCURRENT="${JDYUN_BATCH_MAX_CONCURRENT:-1}"
            -e JDYUN_WORKER_MAX_CONCURRENT="${JDYUN_WORKER_MAX_CONCURRENT:-1}"
            -e JDYUN_STOCK_INTERVAL_SECONDS="${JDYUN_STOCK_INTERVAL_SECONDS:-10}"
        )
    fi

    docker run "${RUN_ARGS[@]}" "${IMAGE_NAME}:${IMAGE_TAG}"

    echo "✅ 容器已启动（$MODE_LABEL）"
    echo ""
    echo "查看日志："
    echo "  bash run.sh --logs"
    echo ""
    if [ "$DEV_MODE" = true ]; then
        echo "💡 开发模式：改完代码后重启后端秒级生效："
        echo "  bash run.sh --restart-be"
        echo ""
    fi
    echo "等待 30 秒后访问: http://localhost:${HOST_PORT:-8082}"
    if [ "${JDYUN_MODE:-false}" != "true" ]; then
        echo ""
        echo "💡 首次使用请在「系统设置」中配置 API Key 和数据源"
    fi
}

action_restart_be() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "❌ 容器 $CONTAINER_NAME 未运行"
        exit 1
    fi
    echo "🔄 重启后端进程..."
    docker exec "$CONTAINER_NAME" s6-svc -r /run/service/backend 2>/dev/null || {
        echo "⚠️  s6-svc 失败，尝试 kill 进程强制重启..."
        docker exec "$CONTAINER_NAME" pkill -f "uvicorn.*app.main" 2>/dev/null || true
    }
    echo "✅ 后端重启信号已发送，等待 10-15 秒后生效"
    echo "   健康检查: curl http://localhost:${HOST_PORT:-8082}/api/health"
}

action_stop() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "🛑 停止容器: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME"
        docker rm "$CONTAINER_NAME"
        echo "✅ 已停止并删除容器"
    else
        echo "ℹ️  容器 $CONTAINER_NAME 不存在"
    fi
}

action_logs() {
    docker logs -f "$CONTAINER_NAME" 2>&1 || {
        echo "❌ 容器 $CONTAINER_NAME 不存在或未运行"
        exit 1
    }
}

action_shell() {
    docker exec -it "$CONTAINER_NAME" /bin/bash || {
        echo "❌ 容器 $CONTAINER_NAME 不存在或未运行"
        exit 1
    }
}

action_status() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        docker ps -a --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        echo "ℹ️  容器 $CONTAINER_NAME 不存在"
    fi
}

action_clean() {
    # 京东云版使用独立的 MongoDB 卷 ta-data
    if [ "$JDYUN_MODE_FLAG" = true ]; then
        VOLUME_MONGO="ta-data"
    fi

    echo "⚠️  警告：将删除以下数据卷："
    echo "   - $VOLUME_MONGO (MongoDB 数据)"
    echo "   - $VOLUME_REDIS (Redis 数据)"
    echo "   - $VOLUME_RUNTIME (运行时配置)"
    echo "   - $VOLUME_LOGS (日志)"
    echo "   - $VOLUME_QDRANT (Qdrant 向量库数据)"
    read -p "确认删除？(yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        action_stop
        docker volume rm "$VOLUME_MONGO" "$VOLUME_REDIS" "$VOLUME_RUNTIME" "$VOLUME_LOGS" "$VOLUME_QDRANT" 2>&1 || true
        echo "✅ 数据卷已清理"
    else
        echo "已取消"
    fi
}

# ------------------------------------------------------------------------------
# 执行
# ------------------------------------------------------------------------------
case "$ACTION" in
    build) action_build ;;
    start) action_start ;;
    stop) action_stop ;;
    logs) action_logs ;;
    shell) action_shell ;;
    status) action_status ;;
    restart-be) action_restart_be ;;
    clean) action_clean ;;
esac
