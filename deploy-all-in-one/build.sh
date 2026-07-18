#!/bin/bash
# TradingAgents-CN Pro 单容器镜像构建脚本
# 用法：bash build.sh [version] [--push] [--single-arch]

set -eu

VERSION="${1:-3.0.0}"
PUSH=false
SINGLE_ARCH=false

# 解析参数
ARGS=()
for arg in "$@"; do
    case "$arg" in
        --push) PUSH=true ;;
        --single-arch) SINGLE_ARCH=true ;;
        *) ARGS+=("$arg") ;;
    esac
done

# 镜像名
IMAGE_NAME="tradingagents-cn-pro"

# 多架构或单架构
if [ "$SINGLE_ARCH" = true ]; then
    PLATFORM="linux/amd64"
else
    PLATFORM="linux/amd64,linux/arm64"
fi

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  TradingAgents-CN Pro 单容器构建"
echo "=========================================="
echo "  版本:     $VERSION"
echo "  镜像:     $IMAGE_NAME:$VERSION"
echo "  架构:     $PLATFORM"
echo "  推送:     $PUSH"
echo "  项目根:   $PROJECT_ROOT"
echo "=========================================="
echo ""

# ------------------------------------------------------------------------------
# 前置检查
# ------------------------------------------------------------------------------
if ! command -v docker &> /dev/null; then
    echo "❌ docker 命令未找到"
    exit 1
fi

# 检查 buildx
if ! docker buildx version &> /dev/null; then
    echo "❌ docker buildx 未安装"
    exit 1
fi

# ------------------------------------------------------------------------------
# 构建（多架构）
# ------------------------------------------------------------------------------
cd "$PROJECT_ROOT"

TAG_ARGS=(
    -t "$IMAGE_NAME:$VERSION"
    -t "$IMAGE_NAME:${VERSION%.*}-latest"
    -t "$IMAGE_NAME:3-latest"
)

if [ "$PUSH" = true ]; then
    echo "🚀 构建并推送镜像..."
    docker buildx build \
        --platform "$PLATFORM" \
        -f deploy-all-in-one/Dockerfile \
        "${TAG_ARGS[@]}" \
        --push \
        .
else
    echo "🔨 构建镜像（仅本地，不推送）..."

    # 单架构构建用默认 builder 即可
    if [ "$SINGLE_ARCH" = true ]; then
        echo "   使用默认 docker builder（单架构）"
        docker build \
            -f deploy-all-in-one/Dockerfile \
            "${TAG_ARGS[@]}" \
            .
    else
        # 多架构构建用 buildx
        BUILDER_NAME="ta-multiarch"
        if ! docker buildx inspect "$BUILDER_NAME" &> /dev/null; then
            echo "   创建 buildx builder: $BUILDER_NAME"
            docker buildx create --name "$BUILDER_NAME" --use
        else
            docker buildx use "$BUILDER_NAME"
        fi

        docker buildx build \
            --platform "$PLATFORM" \
            -f deploy-all-in-one/Dockerfile \
            "${TAG_ARGS[@]}" \
            --load \
            .
    fi
fi

echo ""
echo "=========================================="
echo "  ✅ 构建完成"
echo "=========================================="
echo ""
echo "下一步："
echo "  export MONGODB_PASSWORD='your-password'"
echo "  bash deploy-all-in-one/run.sh"
echo ""
echo "或直接 docker run："
echo "  docker run -d -p 8082:8082 \\"
echo "    -e MONGODB_PASSWORD=xxx \\"
echo "    $IMAGE_NAME:$VERSION"
echo ""
