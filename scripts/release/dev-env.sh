#!/bin/bash
# TradingAgents-CN Pro - 开发环境管理
# 用法: ./dev-env.sh <子命令> <version>
#
# 子命令:
#   up <version>     启动指定版本的开发环境
#   down <version>   停止指定版本的开发环境
#   status           显示所有运行中的开发环境
#
# 版本: 2.0, 2.1, 3.0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.compiled.yml"

# 版本配置映射
declare -A VERSION_CONFIG
VERSION_CONFIG[2.0]="ta-v201|27017|6379|8000|8080"
VERSION_CONFIG[2.1]="ta-v210|27018|6380|8001|8081"
VERSION_CONFIG[3.0]="ta-v3|27019|6381|8002|8082"

# 解析版本配置
# 返回: PROJECT_NAME|MONGODB_PORT|REDIS_PORT|BACKEND_PORT|FRONTEND_PORT
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
    log_info "  MongoDB: $MONGODB_PORT, Redis: $REDIS_PORT, Backend: $BACKEND_PORT, Frontend: $FRONTEND_PORT"

    COMPOSE_PROJECT_NAME="$PROJECT_NAME" \
    MONGODB_PORT="$MONGODB_PORT" \
    REDIS_PORT="$REDIS_PORT" \
    PORT="$BACKEND_PORT" \
    NGINX_PORT="$FRONTEND_PORT" \
    docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d

    log_success "v${version} 开发环境已启动"
    log_info "前端: http://localhost:$FRONTEND_PORT"
    log_info "后端: http://localhost:$BACKEND_PORT"
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
    docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true

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
            echo "    MongoDB: $MONGODB_PORT | Redis: $REDIS_PORT | Backend: $BACKEND_PORT | Frontend: $FRONTEND_PORT"
        else
            echo -e "  v${version}: ${RED}未运行${NC} (项目: $PROJECT_NAME)"
        fi
        echo ""
    done
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
