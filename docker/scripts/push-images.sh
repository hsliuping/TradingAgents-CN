#!/bin/bash
# TradingAgents-CN Pro - Docker 镜像推送脚本
# 推送镜像到 Docker Hub
#
# 使用方法:
#   ./docker/scripts/push-images.sh [OPTIONS]
#
# 选项:
#   -r, --registry REGISTRY   Docker Hub 用户名（默认: hsliup）
#   -t, --tag TAG             镜像标签（默认: latest）
#   -b, --backend-only        只推送后端镜像
#   -f, --frontend-only       只推送前端镜像
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
PUSH_BACKEND=true
PUSH_FRONTEND=true

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
        -b|--backend-only)
            PUSH_FRONTEND=false
            shift
            ;;
        -f|--frontend-only)
            PUSH_BACKEND=false
            shift
            ;;
        -h|--help)
            echo "用法: $0 [OPTIONS]"
            echo ""
            echo "选项:"
            echo "  -r, --registry REGISTRY   Docker Hub 用户名（默认: hsliup）"
            echo "  -t, --tag TAG             镜像标签（默认: latest）"
            echo "  -b, --backend-only        只推送后端镜像"
            echo "  -f, --frontend-only       只推送前端镜像"
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
echo -e "${BLUE}Docker 镜像推送${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}📋 推送配置:${NC}"
echo -e "  Registry: ${YELLOW}$REGISTRY${NC}"
echo -e "  Tag: ${YELLOW}$TAG${NC}"
echo -e "  推送后端: ${YELLOW}$PUSH_BACKEND${NC}"
echo -e "  推送前端: ${YELLOW}$PUSH_FRONTEND${NC}"
echo ""

# 检查 Docker 登录状态
echo -e "${GREEN}🔐 检查 Docker Hub 登录状态...${NC}"
if ! docker info | grep -q "Username"; then
    echo -e "${YELLOW}⚠️  未登录 Docker Hub，请先登录:${NC}"
    echo -e "  ${YELLOW}docker login${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 已登录 Docker Hub${NC}"
echo ""

# 推送后端镜像
if [ "$PUSH_BACKEND" = true ]; then
    BACKEND_IMAGE="$REGISTRY/tradingagents-backend:$TAG"
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}推送后端镜像${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 检查镜像是否存在
    if ! docker images | grep -q "$REGISTRY/tradingagents-backend"; then
        echo -e "${RED}❌ 错误: 后端镜像不存在，请先构建镜像${NC}"
        echo -e "  ${YELLOW}./docker/scripts/build-compile.sh${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}📤 推送镜像: ${YELLOW}$BACKEND_IMAGE${NC}"
    docker push "$BACKEND_IMAGE"
    echo -e "${GREEN}✅ 后端镜像推送完成${NC}"
    echo ""
fi

# 推送前端镜像
if [ "$PUSH_FRONTEND" = true ]; then
    FRONTEND_IMAGE="$REGISTRY/tradingagents-frontend:$TAG"
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}推送前端镜像${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 检查镜像是否存在
    if ! docker images | grep -q "$REGISTRY/tradingagents-frontend"; then
        echo -e "${RED}❌ 错误: 前端镜像不存在，请先构建镜像${NC}"
        echo -e "  ${YELLOW}docker-compose -f docker/docker-compose.compiled.yml build frontend${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}📤 推送镜像: ${YELLOW}$FRONTEND_IMAGE${NC}"
    docker push "$FRONTEND_IMAGE"
    echo -e "${GREEN}✅ 前端镜像推送完成${NC}"
    echo ""
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 推送完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}镜像信息:${NC}"
if [ "$PUSH_BACKEND" = true ]; then
    echo -e "  后端: ${YELLOW}$REGISTRY/tradingagents-backend:$TAG${NC}"
fi
if [ "$PUSH_FRONTEND" = true ]; then
    echo -e "  前端: ${YELLOW}$REGISTRY/tradingagents-frontend:$TAG${NC}"
fi
echo ""
echo -e "${GREEN}下一步:${NC}"
echo -e "  在部署服务器上拉取镜像:"
if [ "$PUSH_BACKEND" = true ]; then
    echo -e "  ${YELLOW}docker pull $REGISTRY/tradingagents-backend:$TAG${NC}"
fi
if [ "$PUSH_FRONTEND" = true ]; then
    echo -e "  ${YELLOW}docker pull $REGISTRY/tradingagents-frontend:$TAG${NC}"
fi
echo -e "  启动服务:"
echo -e "  ${YELLOW}docker-compose -f docker/docker-compose.compiled.yml up -d${NC}"

