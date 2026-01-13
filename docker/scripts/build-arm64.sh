#!/bin/bash
# TradingAgents-CN Pro - ARM64 镜像构建脚本
# 用于在 x86_64 或 ARM64 服务器上构建 ARM64 架构的镜像
# 
# 功能:
# 1. 编译 Python 代码为 .pyc 和 .so
# 2. 构建 ARM64 后端 Docker 镜像（编译版）
# 3. 构建 ARM64 前端 Docker 镜像
# 4. 推送所有镜像到 Docker Hub
#
# 使用方法:
#   ./docker/scripts/build-arm64.sh [OPTIONS]
#
# 选项:
#   -r, --registry REGISTRY   Docker Hub 用户名（默认: hsliup）
#   -t, --tag TAG             镜像标签（默认: latest）
#   --skip-compile            跳过代码编译（使用已有的编译产物）
#   --skip-backend            跳过后端镜像构建
#   --skip-frontend           跳过前端镜像构建
#   --skip-push               只构建不推送
#   --use-qemu                使用 QEMU 模拟器（跨平台构建）
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
SKIP_COMPILE=false
SKIP_BACKEND=false
SKIP_FRONTEND=false
SKIP_PUSH=false
USE_QEMU=false
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
        --skip-compile)
            SKIP_COMPILE=true
            shift
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
        --use-qemu)
            USE_QEMU=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [OPTIONS]"
            echo ""
            echo "选项:"
            echo "  -r, --registry REGISTRY   Docker Hub 用户名（默认: hsliup）"
            echo "  -t, --tag TAG             镜像标签（默认: latest）"
            echo "  --skip-compile            跳过代码编译（使用已有的编译产物）"
            echo "  --skip-backend            跳过后端镜像构建"
            echo "  --skip-frontend           跳过前端镜像构建"
            echo "  --skip-push               只构建不推送"
            echo "  --use-qemu                使用 QEMU 模拟器（跨平台构建）"
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
BACKEND_IMAGE="$REGISTRY/tradingagents-pro-backend:$TAG-arm64"
FRONTEND_IMAGE="$REGISTRY/tradingagents-pro-frontend:$TAG-arm64"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}TradingAgents-CN Pro - ARM64 构建${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "${GREEN}Registry: ${YELLOW}$REGISTRY${NC}"
echo -e "${GREEN}Tag: ${YELLOW}$TAG${NC}"
echo -e "${GREEN}后端镜像: ${YELLOW}$BACKEND_IMAGE${NC}"
echo -e "${GREEN}前端镜像: ${YELLOW}$FRONTEND_IMAGE${NC}"
echo -e "${GREEN}使用 QEMU: ${YELLOW}$USE_QEMU${NC}"
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

# 如果使用 QEMU，安装 QEMU 模拟器
if [ "$USE_QEMU" = true ]; then
    echo -e "${GREEN}🔧 安装 QEMU 模拟器...${NC}"
    docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
fi

# 启动 builder
docker buildx inspect --bootstrap

echo -e "${GREEN}✅ Docker Buildx 设置完成${NC}"
echo ""

# 步骤 1: 编译代码（如果需要）
if [ "$SKIP_COMPILE" = false ] && [ "$SKIP_BACKEND" = false ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}步骤 1: 编译 Python 代码${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # 注意：ARM64 编译需要在 ARM64 环境中进行
    # 如果在 x86_64 上，跳过编译或使用 QEMU
    ARCH=$(uname -m)
    if [ "$ARCH" != "aarch64" ] && [ "$ARCH" != "arm64" ]; then
        echo -e "${YELLOW}⚠️  当前架构是 $ARCH，不是 ARM64${NC}"
        echo -e "${YELLOW}⚠️  跳过代码编译，将在 Docker 构建时编译${NC}"
        SKIP_COMPILE=true
    else
        "$SCRIPT_DIR/compile-code.sh"
        echo -e "${GREEN}✅ 代码编译完成${NC}"
    fi
    echo ""
else
    echo -e "${YELLOW}⏭️  跳过代码编译${NC}"
    echo ""
fi

# 步骤 2: 构建后端镜像
if [ "$SKIP_BACKEND" = false ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}步骤 2: 构建 ARM64 后端镜像${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    echo -e "${GREEN}🐳 构建镜像: ${YELLOW}$BACKEND_IMAGE${NC}"

    docker buildx build \
        --platform linux/arm64 \
        -f "$PROJECT_ROOT/docker/Dockerfile.backend.compiled.ubuntu" \
        -t "$BACKEND_IMAGE" \
        --build-arg COMPILE_DIR="docker/build/compiled" \
        --load \
        "$PROJECT_ROOT"

    echo -e "${GREEN}✅ 后端镜像构建完成${NC}"
    echo ""
else
    echo -e "${YELLOW}⏭️  跳过后端镜像构建${NC}"
    echo ""
fi

# 步骤 3: 构建前端镜像
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}步骤 3: 构建 ARM64 前端镜像${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    echo -e "${GREEN}🐳 构建镜像: ${YELLOW}$FRONTEND_IMAGE${NC}"

    docker buildx build \
        --platform linux/arm64 \
        -f "$PROJECT_ROOT/docker/Dockerfile.frontend" \
        -t "$FRONTEND_IMAGE" \
        --load \
        "$PROJECT_ROOT"

    echo -e "${GREEN}✅ 前端镜像构建完成${NC}"
    echo ""
else
    echo -e "${YELLOW}⏭️  跳过前端镜像构建${NC}"
    echo ""
fi

# 步骤 4: 推送镜像到 Docker Hub
if [ "$SKIP_PUSH" = false ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}步骤 4: 推送镜像到 Docker Hub${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # 推送后端镜像
    if [ "$SKIP_BACKEND" = false ]; then
        echo -e "${GREEN}📤 推送后端镜像: ${YELLOW}$BACKEND_IMAGE${NC}"
        docker push "$BACKEND_IMAGE"
        echo -e "${GREEN}✅ 后端镜像推送完成${NC}"
        echo ""
    fi

    # 推送前端镜像
    if [ "$SKIP_FRONTEND" = false ]; then
        echo -e "${GREEN}📤 推送前端镜像: ${YELLOW}$FRONTEND_IMAGE${NC}"
        docker push "$FRONTEND_IMAGE"
        echo -e "${GREEN}✅ 前端镜像推送完成${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}⏭️  跳过镜像推送${NC}"
    echo ""
fi

# 完成
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ ARM64 构建完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ "$SKIP_BACKEND" = false ]; then
    echo -e "${GREEN}后端镜像: ${YELLOW}$BACKEND_IMAGE${NC}"
fi
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${GREEN}前端镜像: ${YELLOW}$FRONTEND_IMAGE${NC}"
fi
echo ""

echo -e "${GREEN}下一步:${NC}"
if [ "$SKIP_PUSH" = false ]; then
    echo -e "  1. 在 ARM64 服务器上拉取镜像:"
    if [ "$SKIP_BACKEND" = false ]; then
        echo -e "     ${YELLOW}docker pull $BACKEND_IMAGE${NC}"
    fi
    if [ "$SKIP_FRONTEND" = false ]; then
        echo -e "     ${YELLOW}docker pull $FRONTEND_IMAGE${NC}"
    fi
    echo -e "  2. 启动服务:"
    echo -e "     ${YELLOW}docker-compose -f docker/docker-compose.compiled.yml up -d${NC}"
else
    echo -e "  1. 推送镜像到 Docker Hub:"
    if [ "$SKIP_BACKEND" = false ]; then
        echo -e "     ${YELLOW}docker push $BACKEND_IMAGE${NC}"
    fi
    if [ "$SKIP_FRONTEND" = false ]; then
        echo -e "     ${YELLOW}docker push $FRONTEND_IMAGE${NC}"
    fi
fi
echo ""


