#!/bin/bash
# TradingAgents-CN Pro 单容器镜像构建脚本
# 用法：bash build.sh [version] [--push] [--single-arch] [--jdyun] [--skip-frontend]
#
# 参数说明：
#   version          版本号（默认 3.0.0）
#   --push           构建并推送到镜像仓库
#   --single-arch    单架构构建（避免 multiarch 网络超时）
#   --jdyun          京东云版（前端用 --mode jdyun 编译，镜像 tag 加 -jdyun 后缀）
#   --skip-frontend  跳过前端编译（使用已有的 frontend/dist）

set -eu

VERSION="${1:-3.0.0}"
PUSH=false
SINGLE_ARCH=false
JDYUN=false
SKIP_FRONTEND=false

# 解析参数
ARGS=()
for arg in "$@"; do
    case "$arg" in
        --push) PUSH=true ;;
        --single-arch) SINGLE_ARCH=true ;;
        --jdyun) JDYUN=true ;;
        --skip-frontend) SKIP_FRONTEND=true ;;
        *) ARGS+=("$arg") ;;
    esac
done

# 镜像名
IMAGE_NAME="tradingagents-cn-pro"

# 京东云版镜像 tag 加 -jdyun 后缀
if [ "$JDYUN" = true ]; then
    IMAGE_TAG="$VERSION-jdyun"
    MODE_LABEL="京东云版"
else
    IMAGE_TAG="$VERSION"
    MODE_LABEL="普通版"
fi

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
echo "  TradingAgents-CN Pro 单容器构建（$MODE_LABEL）"
echo "=========================================="
echo "  版本:     $VERSION"
echo "  镜像:     $IMAGE_NAME:$IMAGE_TAG"
echo "  架构:     $PLATFORM"
echo "  推送:     $PUSH"
echo "  京东云:   $JDYUN"
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
# 前端编译（在 docker build 之前执行）
# Dockerfile 会 COPY frontend/dist 到镜像中，必须先编译
# ------------------------------------------------------------------------------
cd "$PROJECT_ROOT"

# ------------------------------------------------------------------------------
# 生成 SearXNG wheel（在 docker build 之前执行）
# 从 searxng/ 源码目录打包，Dockerfile 会 COPY 到镜像内安装
# --no-deps：依赖已在基础镜像，避免拉取额外包
# ------------------------------------------------------------------------------
if [ -f "searxng/setup.py" ] || [ -f "searxng/pyproject.toml" ]; then
    echo "📦 生成 SearXNG wheel..."
    mkdir -p deploy-all-in-one/wheels
    rm -f deploy-all-in-one/wheels/searxng-*.whl
    python -m pip wheel ./searxng --no-deps -w deploy-all-in-one/wheels || \
    python3 -m pip wheel ./searxng --no-deps -w deploy-all-in-one/wheels
    if ! ls deploy-all-in-one/wheels/searxng-*.whl &> /dev/null; then
        echo "❌ SearXNG wheel 生成失败"
        exit 1
    fi
    echo "   $(ls deploy-all-in-one/wheels/searxng-*.whl | head -1)"
else
    echo "❌ searxng/ 源码目录不存在（git clone https://github.com/searxng/searxng 后重试）"
    exit 1
fi

# ------------------------------------------------------------------------------
# 更新种子数据中的用户手册签名（确保跨环境签名一致）
# 签名基于文件内容 hash，不依赖路径和 mtime
# ------------------------------------------------------------------------------
if [ -f "deploy-all-in-one/update_seed_signature_local.py" ]; then
    echo "📝 更新种子数据签名..."
    python3 deploy-all-in-one/update_seed_signature_local.py 2>/dev/null || \
    python deploy-all-in-one/update_seed_signature_local.py 2>/dev/null || \
    echo "⚠️  签名更新跳过（需要 Python + 本地手册文件）"
fi

if [ "$SKIP_FRONTEND" = true ]; then
    echo "⏭️  跳过前端编译（--skip-frontend）"
    if [ ! -d "frontend/dist" ]; then
        echo "❌ frontend/dist 不存在，请先执行前端编译或去掉 --skip-frontend 参数"
        exit 1
    fi
else
    echo "📦 编译前端..."
    cd frontend

    if [ "$JDYUN" = true ]; then
        echo "   京东云版：npm run build -- --mode jdyun"
        npm run build -- --mode jdyun
    else
        echo "   普通版：npm run build"
        npm run build
    fi

    cd "$PROJECT_ROOT"

    # 验证编译产物
    if [ ! -f "frontend/dist/index.html" ]; then
        echo "❌ 前端编译失败：frontend/dist/index.html 不存在"
        exit 1
    fi

    # 京东云版验证标识
    if [ "$JDYUN" = true ]; then
        if ! grep -q "京东云" frontend/dist/index.html 2>/dev/null; then
            echo "⚠️  警告：京东云版编译未检测到标识，请确认 .env.jdyun 配置正确"
        else
            echo "✅ 京东云版标识验证通过"
        fi
    fi

    echo "✅ 前端编译完成"
    echo ""
fi

# ------------------------------------------------------------------------------
# 构建 Docker 镜像
# ------------------------------------------------------------------------------
cd "$PROJECT_ROOT"

TAG_ARGS=(
    -t "$IMAGE_NAME:$IMAGE_TAG"
)
# 普通版额外添加 latest 标签（京东云版不加，避免和普通版冲突）
if [ "$JDYUN" = false ]; then
    TAG_ARGS+=(
        -t "$IMAGE_NAME:${VERSION%.*}-latest"
        -t "$IMAGE_NAME:3-latest"
    )
fi

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
echo "  ✅ 构建完成（$MODE_LABEL）"
echo "=========================================="
echo ""
echo "下一步："
if [ "$JDYUN" = true ]; then
    echo "  # 京东云版启动（使用 ta-data 数据卷）"
    echo "  bash deploy-all-in-one/run.sh --jdyun"
    echo ""
    echo "  # 或直接 docker run（需自行加载 .env.docker.jdyun）"
    echo "  docker run -d -p 8082:8082 \\"
    echo "    -v ta-data:/data/db \\"
    echo "    -e JDYUN_MODE=true \\"
    echo "    -e MONGODB_PASSWORD=xxx \\"
    echo "    -e OPENAI_API_KEY=xxx \\"
    echo "    -e TUSHARE_TOKEN=xxx \\"
    echo "    $IMAGE_NAME:$IMAGE_TAG"
else
    echo "  # 普通版启动（使用 ta-mongo-data 数据卷）"
    echo "  export MONGODB_PASSWORD='your-password'"
    echo "  bash deploy-all-in-one/run.sh"
    echo ""
    echo "  # 或直接 docker run"
    echo "  docker run -d -p 8082:8082 \\"
    echo "    -e MONGODB_PASSWORD=xxx \\"
    echo "    $IMAGE_NAME:$IMAGE_TAG"
fi
echo ""
echo "📖 详细配置请参考：deploy-all-in-one/docs/jdyun-branch-guide.md"
echo ""
