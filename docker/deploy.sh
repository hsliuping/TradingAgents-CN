#!/bin/bash
# TradingAgents-CN Pro - 一键部署脚本 (Linux/macOS)
# 版本: v1.2.0
# 用途: 自动下载配置文件、创建目录、启动 Docker 服务
#
# 使用方式:
#   方式1: curl -fsSL https://www.tradingagentscn.com/docker/deploy.sh | bash -s -- [选项]
#   方式2: 下载后运行 bash deploy.sh [选项]
#   如遇 ^M 错误: sed -i 's/\r$//' deploy.sh

set -e  # 遇到错误立即退出

# Docker Compose 命令兼容（优先 V2 插件 docker compose，其次独立版 docker-compose）
detect_compose_cmd() {
    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD=""
    fi
}

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
NGINX_CONFIG_URL="https://www.tradingagentscn.com/docker/nginx-proxy.conf"
DOCKER_COMPOSE_URL="https://www.tradingagentscn.com/docker/docker-compose.compiled.yml"
ENV_DOCKER_URL="https://www.tradingagentscn.com/docker/.env.docker"
DOCKER_COMPOSE_FILE="docker-compose.compiled.yml"

# 默认端口配置
DEFAULT_NGINX_PORT=8082
DEFAULT_MONGODB_PORT=27017
DEFAULT_REDIS_PORT=6379
DEFAULT_BACKEND_PORT=8000
DEFAULT_IMAGE_TAG=latest

# 非交互模式标志
NON_INTERACTIVE=false

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 打印标题
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  TradingAgents-CN Pro 一键部署脚本${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        return 1
    fi
    return 0
}

# 检测操作系统
detect_os() {
    local uname_out
    uname_out="$(uname -s 2>/dev/null)"
    case "$uname_out" in
        Darwin*) echo "macos" ;;
        Linux*)
            if [ -f /etc/os-release ]; then
                . /etc/os-release
                echo "$ID"
            elif command -v lsb_release &>/dev/null; then
                lsb_release -is | tr '[:upper:]' '[:lower:]'
            elif [ -f /etc/redhat-release ]; then
                echo "centos"
            else
                echo "linux"
            fi
            ;;
        *) echo "unknown" ;;
    esac
}

# 安装 Docker
install_docker() {
    local os
    os=$(detect_os)
    print_info "检测到系统: $os"

    case "$os" in
        ubuntu|debian|centos|rhel|rocky|almalinux)
            print_info "使用官方脚本安装 Docker..."
            curl -fsSL https://get.docker.com | sh
            # 启动 Docker 并设置开机自启
            systemctl start docker
            systemctl enable docker
            print_success "Docker 安装完成并已启动"
            ;;
        macos)
            print_info "macOS 系统需要安装 Docker Desktop"
            if check_command brew; then
                print_info "检测到 Homebrew，使用 brew 安装 Docker Desktop..."
                brew install --cask docker
                print_success "Docker Desktop 已安装，请从应用程序中启动"
            else
                print_info "请安装 Docker Desktop:"
                print_info "  方式1: 访问 https://www.docker.com/products/docker-desktop 下载"
                print_info "  方式2: 先安装 Homebrew (https://brew.sh)，然后 brew install --cask docker"
            fi
            print_warning "安装 Docker Desktop 后请重新运行此脚本"
            exit 1
            ;;
        *)
            print_error "不支持的系统: $os，请手动安装 Docker"
            print_info "安装文档: https://docs.docker.com/engine/install/"
            exit 1
            ;;
    esac
}

# 安装 Docker Compose
install_docker_compose() {
    local os
    os=$(detect_os)

    # macOS 上 Docker Desktop 自带 Compose
    if [ "$os" = "macos" ]; then
        print_error "macOS 上 Docker Desktop 自带 Docker Compose，请确保 Docker Desktop 已正确安装并启动"
        exit 1
    fi

    # 检查是否已通过 Docker Compose V2 插件安装
    if docker compose version &>/dev/null; then
        print_success "Docker Compose V2 插件已安装"
        return 0
    fi

    print_info "安装 Docker Compose..."

    case "$os" in
        ubuntu|debian)
            apt-get update -qq && apt-get install -y -qq docker-compose-plugin 2>/dev/null
            if docker compose version &>/dev/null; then
                print_success "Docker Compose V2 插件安装完成"
                return 0
            fi
            print_info "插件安装失败，使用独立版本..."
            ;;
        centos|rhel|rocky|almalinux)
            yum install -y docker-compose-plugin 2>/dev/null
            if docker compose version &>/dev/null; then
                print_success "Docker Compose V2 插件安装完成"
                return 0
            fi
            print_info "插件安装失败，使用独立版本..."
            ;;
    esac

    # 独立版本安装
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64)  arch="x86_64" ;;
        aarch64) arch="aarch64" ;;
        *)       print_error "不支持的架构: $arch"; exit 1 ;;
    esac

    local compose_url="https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${arch}"
    curl -fsSL "$compose_url" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    if docker-compose version &>/dev/null; then
        print_success "Docker Compose 独立版安装完成"
    else
        print_error "Docker Compose 安装失败，请手动安装"
        print_info "安装文档: https://docs.docker.com/compose/install/"
        exit 1
    fi
}

# 检查依赖
check_dependencies() {
    print_info "检查依赖..."

    # 检查 Docker
    if ! check_command docker; then
        print_warning "Docker 未安装"
        print_info "是否自动安装 Docker？(y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            install_docker
        else
            print_error "请先安装 Docker: https://docs.docker.com/engine/install/"
            exit 1
        fi
    else
        print_success "Docker 已安装 ($(docker --version 2>/dev/null))"
    fi

    # 检查 Docker 服务是否运行
    if ! docker info &>/dev/null; then
        print_warning "Docker 服务未运行，尝试启动..."
        local os
        os=$(detect_os)
        if [ "$os" = "macos" ]; then
            # macOS: 尝试打开 Docker Desktop
            open -a Docker 2>/dev/null && {
                print_info "正在启动 Docker Desktop，请等待..."
                # 等待 Docker 就绪（最多 60 秒）
                for i in $(seq 1 30); do
                    sleep 2
                    if docker info &>/dev/null; then
                        print_success "Docker Desktop 已启动"
                        break
                    fi
                done
            } || {
                print_error "无法启动 Docker Desktop，请手动从应用程序中启动"
                exit 1
            }
        else
            systemctl start docker 2>/dev/null || service docker start 2>/dev/null || {
                print_error "无法启动 Docker 服务，请手动启动"
                exit 1
            }
            print_success "Docker 服务已启动"
        fi
        # 最终检查
        if ! docker info &>/dev/null; then
            print_error "Docker 服务仍未运行，请检查后重试"
            exit 1
        fi
    fi

    # 检查 Docker Compose（优先 V2 插件，其次独立版）
    if docker compose version &>/dev/null; then
        print_success "Docker Compose 已安装 ($(docker compose version --short 2>/dev/null))"
    elif check_command docker-compose; then
        print_success "Docker Compose 已安装 ($(docker-compose --version 2>/dev/null))"
    else
        print_warning "Docker Compose 未安装"
        print_info "是否自动安装 Docker Compose？(y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            install_docker_compose
        else
            print_error "请先安装 Docker Compose: https://docs.docker.com/compose/install/"
            exit 1
        fi
    fi

    # 检查 wget 或 curl（至少需要一个用于下载配置文件）
    if check_command wget; then
        print_success "wget 已安装"
    elif check_command curl; then
        print_success "curl 已安装（将替代 wget）"
        # 定义 wget 别名使用 curl
        wget() { curl -fsSL "$1" -o "$2"; }
    else
        print_warning "wget 和 curl 均未安装，正在安装 curl..."
        local os
        os=$(detect_os)
        case "$os" in
            ubuntu|debian) apt-get update -qq && apt-get install -y -qq curl ;;
            centos|rhel|rocky|almalinux) yum install -y curl ;;
            macos)
                if check_command brew; then
                    brew install curl
                else
                    print_error "请先安装 Homebrew (https://brew.sh) 或手动安装 curl"
                    exit 1
                fi
                ;;
            *) print_error "请手动安装 curl 或 wget"; exit 1 ;;
        esac
        wget() { curl -fsSL "$1" -o "$2"; }
    fi

    print_success "依赖检查通过"
}

# 创建必需的目录
create_directories() {
    print_info "创建必需的目录..."
    
    mkdir -p nginx
    print_success "创建 nginx/ 目录"
    
    # logs、data、runtime 会由 Docker 自动创建，但我们也可以提前创建
    mkdir -p logs data runtime
    print_success "创建 logs/、data/、runtime/ 目录"
}

# 询问端口配置
configure_ports() {
    print_info "配置服务端口..."
    echo ""

    if $NON_INTERACTIVE; then
        NGINX_PORT=${NGINX_PORT:-$DEFAULT_NGINX_PORT}
        MONGODB_PORT=${MONGODB_PORT:-$DEFAULT_MONGODB_PORT}
        REDIS_PORT=${REDIS_PORT:-$DEFAULT_REDIS_PORT}
        BACKEND_PORT=${BACKEND_PORT:-$DEFAULT_BACKEND_PORT}
        print_success "Nginx 端口: $NGINX_PORT"
        print_success "MongoDB 端口: $MONGODB_PORT"
        print_success "Redis 端口: $REDIS_PORT"
        print_success "Backend 端口: $BACKEND_PORT"
        echo ""
        print_success "端口配置完成！"
        echo ""
        return
    fi

    # Nginx 端口
    print_info "Nginx 前端服务端口 (默认: $DEFAULT_NGINX_PORT)"
    read -p "请输入端口 [直接回车使用默认]: " NGINX_PORT
    NGINX_PORT=${NGINX_PORT:-$DEFAULT_NGINX_PORT}
    print_success "Nginx 端口: $NGINX_PORT"

    # MongoDB 端口
    print_info "MongoDB 数据库端口 (默认: $DEFAULT_MONGODB_PORT)"
    read -p "请输入端口 [直接回车使用默认]: " MONGODB_PORT
    MONGODB_PORT=${MONGODB_PORT:-$DEFAULT_MONGODB_PORT}
    print_success "MongoDB 端口: $MONGODB_PORT"

    # Redis 端口
    print_info "Redis 缓存端口 (默认: $DEFAULT_REDIS_PORT)"
    read -p "请输入端口 [直接回车使用默认]: " REDIS_PORT
    REDIS_PORT=${REDIS_PORT:-$DEFAULT_REDIS_PORT}
    print_success "Redis 端口: $REDIS_PORT"

    # Backend 端口
    print_info "Backend API 端口 (默认: $DEFAULT_BACKEND_PORT)"
    read -p "请输入端口 [直接回车使用默认]: " BACKEND_PORT
    BACKEND_PORT=${BACKEND_PORT:-$DEFAULT_BACKEND_PORT}
    print_success "Backend 端口: $BACKEND_PORT"

    echo ""
    print_success "端口配置完成！"
    echo ""
}

# 询问部署版本
configure_version() {
    print_info "配置部署版本..."
    echo ""

    if $NON_INTERACTIVE; then
        IMAGE_TAG=${IMAGE_TAG:-$DEFAULT_IMAGE_TAG}
        # 用户输入版本号时可能不带 v 前缀，自动补上
        if [[ "$IMAGE_TAG" =~ ^[0-9] ]]; then
            IMAGE_TAG="v${IMAGE_TAG}"
        fi
        print_success "镜像版本: $IMAGE_TAG"
        echo ""
        return
    fi

    print_info "Docker 镜像版本 (默认: latest，如指定版本请输入如 2.1.0)"
    read -p "请输入版本号 [直接回车使用默认]: " IMAGE_TAG
    IMAGE_TAG=${IMAGE_TAG:-$DEFAULT_IMAGE_TAG}
    # 用户输入版本号时可能不带 v 前缀，自动补上
    if [[ "$IMAGE_TAG" =~ ^[0-9] ]]; then
        IMAGE_TAG="v${IMAGE_TAG}"
    fi
    print_success "镜像版本: $IMAGE_TAG"
    echo ""
}

# 下载 docker-compose.compiled.yml 文件
download_docker_compose() {
    print_info "下载 Docker Compose 配置文件..."

    if [ -f "$DOCKER_COMPOSE_FILE" ]; then
        print_warning "$DOCKER_COMPOSE_FILE 已存在，是否覆盖？(y/n)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            print_info "跳过下载 Docker Compose 配置"
            return
        fi
    fi

    if wget -q --show-progress "$DOCKER_COMPOSE_URL" -O "$DOCKER_COMPOSE_FILE"; then
        print_success "Docker Compose 配置文件下载成功"
    else
        print_error "Docker Compose 配置文件下载失败"
        print_info "请手动下载: $DOCKER_COMPOSE_URL"
        exit 1
    fi
}

# 下载 nginx 配置文件
download_nginx_config() {
    print_info "下载 Nginx 配置文件..."

    if [ -f "nginx/nginx-proxy.conf" ]; then
        print_warning "nginx/nginx-proxy.conf 已存在，是否覆盖？(y/n)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            print_info "跳过下载 Nginx 配置"
            return
        fi
    fi

    if wget -q --show-progress "$NGINX_CONFIG_URL" -O nginx/nginx-proxy.conf; then
        print_success "Nginx 配置文件下载成功"
    else
        print_error "Nginx 配置文件下载失败"
        print_info "请手动下载: $NGINX_CONFIG_URL"
        exit 1
    fi
}

# 下载 .env 配置文件
download_env_file() {
    print_info "下载 .env 配置文件..."

    if [ -f ".env" ]; then
        print_info ".env 文件已存在，将备份旧文件并下载最新模板"
        mv .env ".env.bak.$(date +%Y%m%d%H%M%S)" 2>/dev/null || true
    fi

    if wget -q --show-progress "$ENV_DOCKER_URL" -O .env; then
        print_success ".env 配置文件下载成功"
    else
        print_error ".env 配置文件下载失败"
        print_info "请手动下载: $ENV_DOCKER_URL"
        exit 1
    fi
}

# 更新端口配置到 docker-compose.yml
update_docker_compose_ports() {
    print_info "更新 Docker Compose 端口配置..."

    # 使用 sed 更新端口配置
    sed -i.bak "s/\"27017:27017\"/\"${MONGODB_PORT}:27017\"/g" "$DOCKER_COMPOSE_FILE"
    sed -i.bak "s/\"6379:6379\"/\"${REDIS_PORT}:6379\"/g" "$DOCKER_COMPOSE_FILE"
    sed -i.bak "s/\"8082:8082\"/\"${NGINX_PORT}:8082\"/g" "$DOCKER_COMPOSE_FILE"

    # 删除备份文件
    rm -f "${DOCKER_COMPOSE_FILE}.bak"

    print_success "Docker Compose 端口配置已更新"
}

# 更新端口配置到 .env 文件
update_env_ports() {
    print_info "更新 .env 端口配置..."

    # 更新 .env 文件中的端口和版本配置
    # 使用临时文件方式，避免 .env 文件含 null 字节时 sed/grep 行为异常
    local tmp_env=".env.tmp.$$"
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            MONGODB_PORT=*)  echo "MONGODB_PORT=${MONGODB_PORT}" ;;
            REDIS_PORT=*)    echo "REDIS_PORT=${REDIS_PORT}" ;;
            PORT=*)          echo "PORT=${BACKEND_PORT}" ;;
            NGINX_PORT=*)    echo "NGINX_PORT=${NGINX_PORT}" ;;
            IMAGE_TAG=*)     echo "IMAGE_TAG=${IMAGE_TAG}" ;;
            *)               echo "$line" ;;
        esac
    done < .env > "$tmp_env"

    # 确保 IMAGE_TAG 存在
    if ! grep -q "^IMAGE_TAG=" "$tmp_env" 2>/dev/null; then
        echo "IMAGE_TAG=${IMAGE_TAG}" >> "$tmp_env"
    fi

    mv "$tmp_env" .env
    rm -f .env.bak

    print_success ".env 端口配置已更新"
    print_info "IMAGE_TAG=${IMAGE_TAG}"
}

# 检查 .env 文件是否存在
check_env_file() {
    print_info "检查环境变量文件..."

    if [ ! -f ".env" ]; then
        print_error ".env 文件不存在"
        print_info "请确保已下载 .env 配置文件"
        exit 1
    else
        print_success ".env 文件已存在"
    fi
}

# 启动 Docker 服务
start_docker_services() {
    print_info "启动 Docker 服务..."

    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        print_error "$DOCKER_COMPOSE_FILE 文件不存在"
        exit 1
    fi

    # 强制清理旧容器，避免容器名冲突
    print_info "清理旧容器..."
    docker rm -f tradingagents-mongodb-pro tradingagents-redis-pro tradingagents-backend-pro tradingagents-frontend-pro tradingagents-nginx-pro 2>/dev/null || true
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" down --remove-orphans 2>/dev/null || true

    print_info "拉取镜像 (版本: ${IMAGE_TAG})..."
    IMAGE_TAG="$IMAGE_TAG" $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" pull

    print_info "启动服务 (版本: ${IMAGE_TAG})..."
    IMAGE_TAG="$IMAGE_TAG" $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d
    
    print_success "Docker 服务启动成功"
}

# 显示服务状态
show_status() {
    print_info "服务状态:"
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps
}

# 显示访问信息
show_access_info() {
    echo ""
    print_success "部署完成！"
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  访问信息${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "${BLUE}部署版本:${NC} ${IMAGE_TAG}"
    echo -e "${BLUE}前端地址:${NC} http://localhost:${NGINX_PORT}"
    echo -e "${BLUE}后端API:${NC} http://localhost:${NGINX_PORT}/api"
    echo -e "${BLUE}MongoDB:${NC} localhost:${MONGODB_PORT}"
    echo -e "${BLUE}Redis:${NC} localhost:${REDIS_PORT}"
    echo ""
    echo -e "${BLUE}默认账号:${NC} admin"
    echo -e "${BLUE}默认密码:${NC} admin123"
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo -e "  - 查看日志: $COMPOSE_CMD -f $DOCKER_COMPOSE_FILE logs -f"
    echo -e "  - 停止服务: $COMPOSE_CMD -f $DOCKER_COMPOSE_FILE down"
    echo -e "  - 重启服务: $COMPOSE_CMD -f $DOCKER_COMPOSE_FILE restart"
    echo ""
}

# 主函数
main() {
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --non-interactive) NON_INTERACTIVE=true ;;
            --image-tag) IMAGE_TAG="$2"; shift ;;
            --nginx-port) NGINX_PORT="$2"; shift ;;
            --mongodb-port) MONGODB_PORT="$2"; shift ;;
            --redis-port) REDIS_PORT="$2"; shift ;;
            --backend-port) BACKEND_PORT="$2"; shift ;;
            -h|--help)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项:"
                echo "  --non-interactive    非交互模式，使用默认值或环境变量"
                echo "  --image-tag TAG      指定 Docker 镜像版本"
                echo "  --nginx-port PORT    指定 Nginx 端口"
                echo "  --mongodb-port PORT  指定 MongoDB 端口"
                echo "  --redis-port PORT    指定 Redis 端口"
                echo "  --backend-port PORT  指定 Backend 端口"
                exit 0
                ;;
            *) print_error "未知选项: $1"; exit 1 ;;
        esac
        shift
    done

    print_header

    # 检测 Docker Compose 命令
    detect_compose_cmd

    # 检查依赖
    check_dependencies

    # 配置端口
    configure_ports

    # 配置部署版本
    configure_version

    # 下载 Docker Compose 配置文件
    download_docker_compose

    # 更新 Docker Compose 端口配置
    update_docker_compose_ports

    # 创建目录
    create_directories

    # 下载 Nginx 配置文件
    download_nginx_config

    # 下载 .env 配置文件
    download_env_file

    # 检查 .env 文件是否存在
    check_env_file

    # 更新 .env 端口配置
    update_env_ports

    # 启动服务
    start_docker_services

    # 显示状态
    show_status

    # 显示访问信息
    show_access_info
}

# 运行主函数
main "$@"

