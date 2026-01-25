#!/bin/bash

# TradingAgents-CN Pro - 一键部署脚本 (Linux/macOS)
# 版本: v1.0.0
# 用途: 自动下载配置文件、创建目录、启动 Docker 服务

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
NGINX_CONFIG_URL="https://www.tradingagentscn.com/docker/nginx-proxy.conf"
DOCKER_COMPOSE_URL="https://www.tradingagentscn.com/docker/docker-compose.compiled.yml"
DOCKER_COMPOSE_FILE="docker-compose.compiled.yml"

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
        print_error "$1 未安装，请先安装 $1"
        exit 1
    fi
}

# 检查依赖
check_dependencies() {
    print_info "检查依赖..."
    check_command docker
    check_command docker-compose
    check_command wget
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

# 检查并创建 .env 文件
setup_env_file() {
    print_info "配置环境变量文件..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_success "已从 .env.example 创建 .env 文件"
            print_warning "请编辑 .env 文件，配置必要的环境变量"
            print_info "按回车键继续编辑 .env 文件，或输入 'skip' 跳过"
            read -r response
            if [[ ! "$response" == "skip" ]]; then
                ${EDITOR:-nano} .env
            fi
        else
            print_error ".env.example 文件不存在"
            exit 1
        fi
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
    
    print_info "拉取最新镜像..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" pull
    
    print_info "启动服务..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    print_success "Docker 服务启动成功"
}

# 显示服务状态
show_status() {
    print_info "服务状态:"
    docker-compose -f "$DOCKER_COMPOSE_FILE" ps
}

# 显示访问信息
show_access_info() {
    echo ""
    print_success "部署完成！"
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  访问信息${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "${BLUE}前端地址:${NC} http://localhost:8082"
    echo -e "${BLUE}后端API:${NC} http://localhost:8082/api"
    echo -e "${BLUE}默认账号:${NC} admin"
    echo -e "${BLUE}默认密码:${NC} admin123"
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo -e "  - 查看日志: docker-compose -f $DOCKER_COMPOSE_FILE logs -f"
    echo -e "  - 停止服务: docker-compose -f $DOCKER_COMPOSE_FILE down"
    echo -e "  - 重启服务: docker-compose -f $DOCKER_COMPOSE_FILE restart"
    echo ""
}

# 主函数
main() {
    print_header

    # 检查依赖
    check_dependencies

    # 下载 Docker Compose 配置文件
    download_docker_compose

    # 创建目录
    create_directories

    # 下载 Nginx 配置文件
    download_nginx_config

    # 配置环境变量
    setup_env_file

    # 启动服务
    start_docker_services

    # 显示状态
    show_status

    # 显示访问信息
    show_access_info
}

# 运行主函数
main

