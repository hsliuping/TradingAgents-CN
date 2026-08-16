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
# 检查 searxng/ 源码目录（wheel 生成现已移入 Dockerfile 阶段 0，复用后端基础镜像）
# 不再依赖本地 Python 环境，避免 docker run 新 Python 镜像造成 apt/pip 网络问题
# ------------------------------------------------------------------------------
if [ ! -f "searxng/setup.py" ] && [ ! -f "searxng/pyproject.toml" ]; then
    echo "❌ searxng/ 源码目录不存在（git clone https://github.com/searxng/searxng 后重试）"
    exit 1
fi
echo "🔍 searxng 源码就绪，wheel 生成将在 docker build 阶段执行（复用后端基础镜像）"

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

    # v3.0 前端用 ?raw 静态导入 30 个课程 + 用户手册，Vite 打包时 bundle 很大
    # 需放大 Node.js V8 堆上限，否则 JS heap OOM（默认约 2GB，容易顶满）
    export NODE_OPTIONS="${NODE_OPTIONS:-} --max-old-space-size=8192"
    export NODE_ENV=production

    # 在 Windows/WSL 混合环境下，优先用 Windows 本地 npm 编译前端
    # （node_modules 通常在 Windows 侧安装，WSL Linux npm 会缺平台二进制导致
    #  rollup/vue-tsc 等一系列跨平台问题；npm.exe 互操作可直接复用 Windows 环境）
    USE_WINDOWS_NPM=false
    if command -v npm.exe >/dev/null 2>&1; then
        USE_WINDOWS_NPM=true
        echo "   检测到 Windows 本地 npm，使用 Windows 环境编译前端（复用 Windows 侧 node_modules）"
    fi

    # 检查 rollup 可选依赖是否匹配当前平台（仅在使用 WSL/Linux npm 时需要；
    # Windows npm.exe 天然匹配 Windows 安装的 node_modules）
    ROLLUP_PLATFORM_PKG=""
    if [ "$USE_WINDOWS_NPM" = false ]; then
        case "$(uname -s)-$(uname -m)" in
            Linux-x86_64)  ROLLUP_PLATFORM_PKG="@rollup/rollup-linux-x64-gnu" ;;
            Linux-aarch64) ROLLUP_PLATFORM_PKG="@rollup/rollup-linux-arm64-gnu" ;;
            Darwin-x86_64) ROLLUP_PLATFORM_PKG="@rollup/rollup-darwin-x64" ;;
            Darwin-arm64)  ROLLUP_PLATFORM_PKG="@rollup/rollup-darwin-arm64" ;;
        esac
    fi
    if [ -n "$ROLLUP_PLATFORM_PKG" ] && [ ! -d "node_modules/$ROLLUP_PLATFORM_PKG" ]; then
        echo "   ⚠️  缺少 $ROLLUP_PLATFORM_PKG（node_modules/ 非本机平台安装），正在补齐..."
        npm install --silent --no-save --include=optional "$ROLLUP_PLATFORM_PKG" || \
            npm install --silent --no-save "$ROLLUP_PLATFORM_PKG" || \
            echo "   （补齐失败，尝试直接构建；若仍报错请删除 frontend/node_modules 后重新 npm install）"
    fi

    NPM_CMD="npm"
    if [ "$USE_WINDOWS_NPM" = true ]; then
        NPM_CMD="npm.exe"
        # NODE_OPTIONS 需通过 WSLENV 才能传递给 Windows 进程
        export WSLENV="${WSLENV:+$WSLENV:}NODE_OPTIONS"
    fi

    if [ "$JDYUN" = true ]; then
        echo "   京东云版：$NPM_CMD run build -- --mode jdyun（NODE_OPTIONS=--max-old-space-size=8192）"
        "$NPM_CMD" run build -- --mode jdyun
    else
        echo "   普通版：$NPM_CMD run build（NODE_OPTIONS=--max-old-space-size=8192）"
        "$NPM_CMD" run build
    fi

    cd "$PROJECT_ROOT"

    # 验证编译产物
    if [ ! -f "frontend/dist/index.html" ]; then
        echo "❌ 前端编译失败：frontend/dist/index.html 不存在"
        exit 1
    fi

    # 京东云版验证：检查 index.html 标题是否包含“京东云版”
    # （VITE_APP_TITLE 由 .env.jdyun 在 jdyun 模式下注入；通用模式编译的产物不含此标识）
    if [ "$JDYUN" = true ]; then
        if ! grep -q "京东云版" frontend/dist/index.html 2>/dev/null; then
            echo "❌ 京东云版编译失败：index.html 标题未包含“京东云版”"
            echo "   原因：vite 未加载 frontend/.env.jdyun（检查 --mode jdyun 是否生效），"
            echo "   或复用了通用模式的旧 dist（不要 --skip-frontend）"
            exit 1
        else
            echo "✅ 京东云版标识验证通过（index.html 标题含“京东云版”）"
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
