#!/bin/bash
# TradingAgents-CN Pro - 编译版 Docker 镜像构建脚本
# 用于在 Ubuntu 22.04 服务器上构建编译版镜像
# 
# 功能:
# 1. 在容器内编译 Python 代码为 .pyc 和 .pyd
# 2. 构建包含编译代码的 Docker 镜像
# 3. 推送到 Docker Hub
#
# 使用方法:
#   ./docker/scripts/build-compile.sh [OPTIONS]
#
# 选项:
#   -r, --registry REGISTRY   Docker Hub 用户名（默认: hsliup）
#   -t, --tag TAG             镜像标签（默认: latest）
#   -p, --push                构建后推送到 Docker Hub
#   -h, --help                显示帮助信息

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认参数
REGISTRY="hsliup"
TAG="latest"
PUSH=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -p|--push)
            PUSH=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [OPTIONS]"
            echo ""
            echo "选项:"
            echo "  -r, --registry REGISTRY   Docker Hub 用户名（默认: hsliup）"
            echo "  -t, --tag TAG             镜像标签（默认: latest）"
            echo "  -p, --push                构建后推送到 Docker Hub"
            echo "  -h, --help                显示帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 未知参数: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TradingAgents-CN Pro - 编译版镜像构建${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}📋 构建配置:${NC}"
echo -e "  Registry: ${YELLOW}$REGISTRY${NC}"
echo -e "  Tag: ${YELLOW}$TAG${NC}"
echo -e "  Push: ${YELLOW}$PUSH${NC}"
echo -e "  Project Root: ${YELLOW}$PROJECT_ROOT${NC}"
echo ""

# 检查是否在项目根目录
if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    echo -e "${RED}❌ 错误: 未找到 pyproject.toml，请确保在项目根目录运行此脚本${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"

# 步骤 1: 编译 Python 代码
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 1: 编译 Python 代码${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 调用编译脚本
if [ -f "$SCRIPT_DIR/compile-code.sh" ]; then
    bash "$SCRIPT_DIR/compile-code.sh"
else
    echo -e "${RED}❌ 错误: 未找到编译脚本 compile-code.sh${NC}"
    exit 1
fi

COMPILE_DIR="$PROJECT_ROOT/docker/build/compiled"

# 检查编译结果
if [ ! -d "$COMPILE_DIR" ]; then
    echo -e "${RED}❌ 错误: 编译目录不存在${NC}"
    exit 1
fi

echo ""

# 步骤 2: 构建 Docker 镜像
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 2: 构建 Docker 镜像${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

IMAGE_NAME="$REGISTRY/tradingagents-pro-backend:$TAG"

echo -e "${GREEN}🐳 构建镜像: ${YELLOW}$IMAGE_NAME${NC}"

# 使用 Dockerfile.backend.compiled.ubuntu
docker build \
    -f "$PROJECT_ROOT/docker/Dockerfile.backend.compiled.ubuntu" \
    -t "$IMAGE_NAME" \
    --build-arg COMPILE_DIR="docker/build/compiled" \
    "$PROJECT_ROOT"

echo -e "${GREEN}✅ 镜像构建完成${NC}"
echo ""

# 步骤 3: 推送到 Docker Hub（可选）
if [ "$PUSH" = true ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}步骤 3: 推送镜像到 Docker Hub${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    echo -e "${GREEN}📤 推送镜像: ${YELLOW}$IMAGE_NAME${NC}"
    docker push "$IMAGE_NAME"
    
    echo -e "${GREEN}✅ 镜像推送完成${NC}"
    echo ""
fi

# 清理临时文件
echo -e "${GREEN}🧹 清理临时文件...${NC}"
rm -rf "$COMPILE_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 构建完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}镜像名称: ${YELLOW}$IMAGE_NAME${NC}"
echo ""
echo -e "${GREEN}下一步:${NC}"
if [ "$PUSH" = true ]; then
    echo -e "  1. 在部署服务器上拉取镜像:"
    echo -e "     ${YELLOW}docker pull $IMAGE_NAME${NC}"
    echo -e "  2. 启动服务:"
    echo -e "     ${YELLOW}docker-compose -f docker/docker-compose.hub.nginx.yml up -d${NC}"
else
    echo -e "  1. 推送镜像到 Docker Hub:"
    echo -e "     ${YELLOW}docker push $IMAGE_NAME${NC}"
    echo -e "  2. 或者直接在本地启动:"
    echo -e "     ${YELLOW}docker-compose -f docker/docker-compose.hub.nginx.yml up -d${NC}"
fi

