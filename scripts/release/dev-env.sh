#!/bin/bash
# TradingAgents-CN Pro - 开发环境管理
# 用法: ./dev-env.sh <子命令> <version>
#
# 子命令:
#   up <version>     启动指定版本的开发环境（MongoDB + Redis）
#   down <version>   停止指定版本的开发环境
#   status           显示所有运行中的开发环境
#
# 版本: 2.0, 2.1, 3.0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.dev.yml"

# 版本配置映射
# 格式: 项目名|MongoDB端口|Redis端口|Backend端口|Frontend端口
declare -A VERSION_CONFIG
VERSION_CONFIG[2.0]="ta-v201|27017|6379|8000|3000"
VERSION_CONFIG[2.1]="ta-v210|27018|6380|8001|3001"
VERSION_CONFIG[3.0]="ta-v3|27019|6381|8002|3002"

# 解析版本配置
get_version_config() {
    local version="$1"
    if [ -z "${VERSION_CONFIG[$version]}" ]; then
        log_error "未知版本: $version (可选: 2.0, 2.1, 3.0)"
        exit 1
    fi
    echo "${VERSION_CONFIG[$version]}"
}

# ==========================================
# up 子命令
# ==========================================
cmd_up() {
    local version="$1"
    if [ -z "$version" ]; then
        log_error "请指定版本，如: dev-env.sh up 2.1"
        exit 1
    fi

    local config
    config=$(get_version_config "$version") || exit 1
    IFS='|' read -r PROJECT_NAME MONGODB_PORT REDIS_PORT BACKEND_PORT FRONTEND_PORT <<< "$config"

    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose 文件不存在: $COMPOSE_FILE"
        exit 1
    fi

    log_info "启动 v${version} 开发环境..."
    log_info "  项目名: $PROJECT_NAME"
    log_info "  MongoDB: localhost:$MONGODB_PORT"
    log_info "  Redis:   localhost:$REDIS_PORT"

    MONGODB_PORT="$MONGODB_PORT" \
    REDIS_PORT="$REDIS_PORT" \
    docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d

    log_success "v${version} 开发环境已启动"
    echo ""
    echo "连接信息:"
    echo "  MongoDB:  mongodb://admin:tradingagents123@localhost:$MONGODB_PORT/tradingagents?authSource=admin"
    echo "  Redis:    redis://:tradingagents123@localhost:$REDIS_PORT/0"
    echo ""
    echo "应用端口 (需通过 start_dev.ps1 / start_dev.py 启动):"
    echo "  Backend:  http://127.0.0.1:$BACKEND_PORT"
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
}

# ==========================================
# down 子命令
# ==========================================
cmd_down() {
    local version="$1"
    if [ -z "$version" ]; then
        log_error "请指定版本，如: dev-env.sh down 2.1"
        exit 1
    fi

    local config
    config=$(get_version_config "$version") || exit 1
    IFS='|' read -r PROJECT_NAME _ _ _ _ <<< "$config"

    log_info "停止 v${version} 开发环境..."
    docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down 2>/dev/null || true

    log_success "v${version} 开发环境已停止"
}

# ==========================================
# status 子命令
# ==========================================
cmd_status() {
    echo "========================================="
    echo "  开发环境状态"
    echo "========================================="
    echo ""

    for version in "2.0" "2.1" "3.0"; do
        local config
        config=$(get_version_config "$version")
        IFS='|' read -r PROJECT_NAME MONGODB_PORT REDIS_PORT BACKEND_PORT FRONTEND_PORT <<< "$config"

        # 检查是否有该项目的容器在运行
        local running
        running=$(docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps -q 2>/dev/null | head -1)

        if [ -n "$running" ]; then
            echo -e "  v${version}: ${GREEN}运行中${NC} (项目: $PROJECT_NAME)"
            echo "    MongoDB: $MONGODB_PORT | Redis: $REDIS_PORT"
        else
            echo -e "  v${version}: ${RED}未运行${NC} (项目: $PROJECT_NAME)"
        fi
        echo "    应用端口: Backend=$BACKEND_PORT | Frontend=$FRONTEND_PORT"
        echo ""
    done

    # 也检查当前运行的独立容器
    echo "其他 TradingAgents 相关容器:"
    docker ps --filter "name=tradingagents" --format "  {{.Names}}\t{{.Ports}}\t{{.Status}}" 2>/dev/null || true
}

# ==========================================
# 主入口
# ==========================================
usage() {
    echo "用法: $0 <子命令> [选项]"
    echo ""
    echo "子命令:"
    echo "  up <version>     启动指定版本的开发环境 (2.0, 2.1, 3.0)"
    echo "  down <version>   停止指定版本的开发环境"
    echo "  status           显示所有运行中的开发环境"
}

case "${1:-}" in
    up)     shift; cmd_up "$@" ;;
    down)   shift; cmd_down "$@" ;;
    status) shift; cmd_status "$@" ;;
    *)      usage; exit 1 ;;
esac
