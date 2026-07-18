#!/bin/bash
# TradingAgents-CN Pro 单容器启动脚本
# 用法：bash run.sh [--build] [--stop] [--logs] [--shell]

set -eu

IMAGE_NAME="${IMAGE_NAME:-tradingagents-cn-pro}"
IMAGE_TAG="${IMAGE_TAG:-3.0.0}"
CONTAINER_NAME="${CONTAINER_NAME:-tradingagents}"
HOST_PORT="${HOST_PORT:-8082}"

# 数据卷名
VOLUME_MONGO="ta-mongo-data"
VOLUME_REDIS="ta-redis-data"
VOLUME_RUNTIME="ta-runtime"
VOLUME_LOGS="ta-logs"

show_help() {
    cat <<EOF
用法: bash run.sh [选项]

选项:
  --build         先构建镜像再启动
  --stop          停止并删除容器
  --logs          查看容器日志
  --shell         进入容器 shell
  --status        查看容器状态
  --clean         清理所有数据卷（危险！）
  --help          显示此帮助

环境变量:
  IMAGE_NAME      镜像名 (默认: tradingagents-cn-pro)
  IMAGE_TAG       镜像标签 (默认: 3.0.0)
  CONTAINER_NAME  容器名 (默认: tradingagents)
  HOST_PORT       宿主机端口 (默认: 8082)
  MONGODB_PASSWORD  MongoDB 密码 (必填)
  REDIS_PASSWORD    Redis 密码 (可选)
  TUSHARE_TOKEN     Tushare Token (可选)

示例:
  export MONGODB_PASSWORD="my-secret-pwd"
  bash run.sh --build
  bash run.sh --logs
  bash run.sh --stop
EOF
}

check_required_env() {
    if [ -z "${MONGODB_PASSWORD:-}" ]; then
        echo "❌ 错误：MONGODB_PASSWORD 环境变量未设置"
        echo "   请先执行: export MONGODB_PASSWORD='your-password'"
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# 参数解析
# ------------------------------------------------------------------------------
ACTION="start"
while [ $# -gt 0 ]; do
    case "$1" in
        --build) ACTION="build"; shift ;;
        --stop) ACTION="stop"; shift ;;
        --logs) ACTION="logs"; shift ;;
        --shell) ACTION="shell"; shift ;;
        --status) ACTION="status"; shift ;;
        --clean) ACTION="clean"; shift ;;
        --help|-h) show_help; exit 0 ;;
        *) echo "未知参数: $1"; show_help; exit 1 ;;
    esac
done

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
    bash "$(dirname "${BASH_SOURCE[0]}")/build.sh" "$IMAGE_TAG"
    action_start
}

action_start() {
    check_required_env
    check_image

    # 停止已存在的同名容器
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "🛑 停止已存在的容器: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME" &> /dev/null || true
        docker rm "$CONTAINER_NAME" &> /dev/null || true
    fi

    echo "=========================================="
    echo "  🚀 启动单容器"
    echo "=========================================="
    echo "  镜像:     ${IMAGE_NAME}:${IMAGE_TAG}"
    echo "  容器:     $CONTAINER_NAME"
    echo "  端口:     http://localhost:$HOST_PORT"
    echo "=========================================="
    echo ""

    docker run -d \
        --name "$CONTAINER_NAME" \
        --hostname tradingagents \
        --restart unless-stopped \
        -p "${HOST_PORT}:8082" \
        -v "${VOLUME_MONGO}:/data/db" \
        -v "${VOLUME_REDIS}:/var/lib/redis" \
        -v "${VOLUME_RUNTIME}:/app/runtime" \
        -v "${VOLUME_LOGS}:/app/logs" \
        -e MONGODB_PASSWORD="$MONGODB_PASSWORD" \
        -e REDIS_PASSWORD="${REDIS_PASSWORD:-}" \
        -e TUSHARE_TOKEN="${TUSHARE_TOKEN:-}" \
        -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
        -e OPENAI_API_BASE="${OPENAI_API_BASE:-}" \
        -e OPENAI_MODEL="${OPENAI_MODEL:-}" \
        -e JDYUN_MODE="${JDYUN_MODE:-false}" \
        -e TZ="${TZ:-Asia/Shanghai}" \
        "${IMAGE_NAME}:${IMAGE_TAG}"

    echo "✅ 容器已启动"
    echo ""
    echo "查看日志："
    echo "  bash run.sh --logs"
    echo ""
    echo "等待 30 秒后访问: http://localhost:$HOST_PORT"
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
    echo "⚠️  警告：将删除以下数据卷："
    echo "   - $VOLUME_MONGO"
    echo "   - $VOLUME_REDIS"
    echo "   - $VOLUME_RUNTIME"
    echo "   - $VOLUME_LOGS"
    read -p "确认删除？(yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        action_stop
        docker volume rm "$VOLUME_MONGO" "$VOLUME_REDIS" "$VOLUME_RUNTIME" "$VOLUME_LOGS" 2>&1 || true
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
    clean) action_clean ;;
esac
