#!/bin/bash
# TradingAgents-CN Pro - 多架构镜像构建脚本
# 同时构建 AMD64 和 ARM64 架构的镜像
# 
# 功能:
# 1. 构建多架构后端 Docker 镜像（AMD64 + ARM64）
# 2. 构建多架构前端 Docker 镜像（AMD64 + ARM64）
# 3. 推送 manifest 到 Docker Hub（自动选择架构）
#
# 使用方法:
#   ./docker/scripts/build-multiarch.sh [OPTIONS]
#
# 选项:
#   -r, --registry REGISTRY   Docker Hub 用户名（默认: hsliup）
#   -t, --tag TAG             镜像标签（默认: latest）
#   --skip-backend            跳过后端镜像构建
#   --skip-frontend           跳过前端镜像构建
#   --skip-push               只构建不推送
#   -h, --help                显示帮助信息

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 默认参数
REGISTRY="hsliup"
TAG="latest"
SKIP_BACKEND=false
SKIP_FRONTEND=false
SKIP_PUSH=false
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
        --skip-backend)
            SKIP_BACKEND=true
            shift
            ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        --skip-push)
            SKIP_PUSH=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [OPTIONS]"
            echo ""
            echo "选项:"
            echo "  -r, --registry REGISTRY   Docker Hub 用户名（默认: hsliup）"
            echo "  -t, --tag TAG             镜像标签（默认: latest）"
            echo "  --skip-backend            跳过后端镜像构建"
            echo "  --skip-frontend           跳过前端镜像构建"
            echo "  --skip-push               只构建不推送"
            echo "  -h, --help                显示帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 未知参数: $1${NC}"
            exit 1
            ;;
    esac
done

# 镜像名称
BACKEND_IMAGE="$REGISTRY/tradingagents-pro-backend:$TAG"
FRONTEND_IMAGE="$REGISTRY/tradingagents-pro-frontend:$TAG"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}TradingAgents-CN Pro - 多架构构建${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "${GREEN}Registry: ${YELLOW}$REGISTRY${NC}"
echo -e "${GREEN}Tag: ${YELLOW}$TAG${NC}"
echo -e "${GREEN}后端镜像: ${YELLOW}$BACKEND_IMAGE${NC}"
echo -e "${GREEN}前端镜像: ${YELLOW}$FRONTEND_IMAGE${NC}"
echo -e "${GREEN}架构: ${YELLOW}linux/amd64, linux/arm64${NC}"
echo ""

# 检查并设置 Docker Buildx
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 0: 设置 Docker Buildx${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 buildx 是否可用
if ! docker buildx version &> /dev/null; then
    echo -e "${RED}❌ Docker Buildx 不可用，请升级 Docker 到 19.03 或更高版本${NC}"
    exit 1
fi

# 创建或使用 multiarch builder
if ! docker buildx inspect multiarch &> /dev/null; then
    echo -e "${GREEN}📦 创建 multiarch builder...${NC}"
    docker buildx create --name multiarch --use
else
    echo -e "${GREEN}📦 使用现有的 multiarch builder...${NC}"
    docker buildx use multiarch
fi

# 安装 QEMU 模拟器（用于跨平台构建）
echo -e "${GREEN}🔧 安装 QEMU 模拟器...${NC}"
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

# 启动 builder
docker buildx inspect --bootstrap

echo -e "${GREEN}✅ Docker Buildx 设置完成${NC}"
echo ""

# 构建参数
PUSH_FLAG=""
if [ "$SKIP_PUSH" = false ]; then
    PUSH_FLAG="--push"
else
    echo -e "${YELLOW}⚠️  注意：多架构构建不支持 --load，将自动推送到 Docker Hub${NC}"
    PUSH_FLAG="--push"
fi

# 步骤 1: 构建后端镜像
if [ "$SKIP_BACKEND" = false ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}步骤 1: 构建多架构后端镜像${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    echo -e "${GREEN}🐳 构建镜像: ${YELLOW}$BACKEND_IMAGE${NC}"
    echo -e "${GREEN}📦 架构: ${YELLOW}linux/amd64, linux/arm64${NC}"

    docker buildx build \
        --platform linux/amd64,linux/arm64 \
        -f "$PROJECT_ROOT/docker/Dockerfile.backend.compiled.ubuntu" \
        -t "$BACKEND_IMAGE" \
        $PUSH_FLAG \
        "$PROJECT_ROOT"

    echo -e "${GREEN}✅ 后端镜像构建完成${NC}"
    echo ""
else
    echo -e "${YELLOW}⏭️  跳过后端镜像构建${NC}"
    echo ""
fi

# 步骤 2: 构建前端镜像
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}步骤 2: 构建多架构前端镜像${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    echo -e "${GREEN}🐳 构建镜像: ${YELLOW}$FRONTEND_IMAGE${NC}"
    echo -e "${GREEN}📦 架构: ${YELLOW}linux/amd64, linux/arm64${NC}"

    docker buildx build \
        --platform linux/amd64,linux/arm64 \
        -f "$PROJECT_ROOT/docker/Dockerfile.frontend" \
        -t "$FRONTEND_IMAGE" \
        $PUSH_FLAG \
        "$PROJECT_ROOT"

    echo -e "${GREEN}✅ 前端镜像构建完成${NC}"
    echo ""
else
    echo -e "${YELLOW}⏭️  跳过前端镜像构建${NC}"
    echo ""
fi

# 完成
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 多架构构建完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ "$SKIP_BACKEND" = false ]; then
    echo -e "${GREEN}后端镜像: ${YELLOW}$BACKEND_IMAGE${NC}"
    echo -e "  - linux/amd64"
    echo -e "  - linux/arm64"
fi
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${GREEN}前端镜像: ${YELLOW}$FRONTEND_IMAGE${NC}"
    echo -e "  - linux/amd64"
    echo -e "  - linux/arm64"
fi
echo ""

echo -e "${GREEN}下一步:${NC}"
echo -e "  1. 在任意架构的服务器上拉取镜像（自动选择架构）:"
if [ "$SKIP_BACKEND" = false ]; then
    echo -e "     ${YELLOW}docker pull $BACKEND_IMAGE${NC}"
fi
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "     ${YELLOW}docker pull $FRONTEND_IMAGE${NC}"
fi
echo -e "  2. 启动服务:"
echo -e "     ${YELLOW}docker-compose -f docker/docker-compose.compiled.yml up -d${NC}"
echo ""
echo -e "${CYAN}💡 提示: Docker 会自动选择与当前系统架构匹配的镜像${NC}"
echo ""


