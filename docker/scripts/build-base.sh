#!/bin/bash
# TradingAgents-CN Pro - 后端基础镜像构建脚本
# 默认本机构建当前架构镜像；指定 --push 后构建并推送多架构基础镜像

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

REGISTRY="hsliup"
TAG="python3.10-bookworm"
PUSH=false
PLATFORMS="linux/amd64,linux/arm64"
APT_MIRROR="https://mirrors.tuna.tsinghua.edu.cn/debian"
APT_SECURITY_MIRROR="https://mirrors.tuna.tsinghua.edu.cn/debian-security"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

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
        --push)
            PUSH=true
            shift
            ;;
        --platforms)
            PLATFORMS="$2"
            shift 2
            ;;
        --apt-mirror)
            APT_MIRROR="$2"
            shift 2
            ;;
        --apt-security-mirror)
            APT_SECURITY_MIRROR="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: $0 [OPTIONS]"
            echo ""
            echo "选项:"
            echo "  -r, --registry REGISTRY   Docker Hub 用户名（默认: hsliup）"
            echo "  -t, --tag TAG             基础镜像标签（默认: python3.10-bookworm）"
            echo "  --push                    使用 buildx 构建并推送多架构基础镜像"
            echo "  --platforms PLATFORMS     多架构平台列表（默认: linux/amd64,linux/arm64）"
            echo "  --apt-mirror URL          Debian 主镜像（默认: 清华镜像）"
            echo "  --apt-security-mirror URL Debian 安全更新镜像（默认: 清华镜像）"
            echo "  -h, --help                显示帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 未知参数: $1${NC}"
            exit 1
            ;;
    esac
done

IMAGE_NAME="$REGISTRY/tradingagents-pro-backend-base:$TAG"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}TradingAgents-CN Pro - 后端基础镜像构建${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "${GREEN}镜像: ${YELLOW}$IMAGE_NAME${NC}"
echo -e "${GREEN}Push: ${YELLOW}$PUSH${NC}"
echo -e "${GREEN}APT mirror: ${YELLOW}$APT_MIRROR${NC}"
echo -e "${GREEN}APT security mirror: ${YELLOW}$APT_SECURITY_MIRROR${NC}"
if [ "$PUSH" = true ]; then
    echo -e "${GREEN}Platforms: ${YELLOW}$PLATFORMS${NC}"
fi
echo ""

cd "$PROJECT_ROOT"

if [ "$PUSH" = true ]; then
    if ! docker buildx version &> /dev/null; then
        echo -e "${RED}❌ Docker Buildx 不可用，请升级 Docker${NC}"
        exit 1
    fi

    if ! docker buildx inspect multiarch &> /dev/null; then
        docker buildx create --name multiarch --use
    else
        docker buildx use multiarch
    fi

    docker buildx inspect --bootstrap >/dev/null

    docker buildx build \
        --platform "$PLATFORMS" \
        -f "$PROJECT_ROOT/docker/Dockerfile.backend.base.ubuntu" \
        -t "$IMAGE_NAME" \
        --build-arg APT_MIRROR="$APT_MIRROR" \
        --build-arg APT_SECURITY_MIRROR="$APT_SECURITY_MIRROR" \
        --push \
        "$PROJECT_ROOT"
else
    docker build \
        -f "$PROJECT_ROOT/docker/Dockerfile.backend.base.ubuntu" \
        -t "$IMAGE_NAME" \
        --build-arg APT_MIRROR="$APT_MIRROR" \
        --build-arg APT_SECURITY_MIRROR="$APT_SECURITY_MIRROR" \
        "$PROJECT_ROOT"
fi

echo ""
echo -e "${GREEN}✅ 基础镜像构建完成: ${YELLOW}$IMAGE_NAME${NC}"
