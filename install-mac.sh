#!/usr/bin/env bash
# =============================================================================
# TradingAgents-CN macOS 一键安装脚本（社区版）
#
# 用途：一条命令装齐运行环境并完成首次构建
#   1. Homebrew（缺失时自动安装）
#   2. Python 3.11 / Node.js / MongoDB / Redis（brew 托管，开机自启）
#   3. 后端 Python 虚拟环境 + 依赖
#   4. .env 配置文件（本地学习默认配置，JWT 密钥随机生成）
#   5. 前端依赖安装与构建（frontend/dist）
#
# 安装完成后运行：bash start.sh 启动系统
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

echo "==> TradingAgents-CN macOS 一键安装"
echo "    仓库目录: $REPO_DIR"

# -----------------------------------------------------------------------------
# 1. Homebrew
# -----------------------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
    echo "==> 未检测到 Homebrew，开始安装（需要输入开机密码）..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon: /opt/homebrew；Intel: /usr/local
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

# -----------------------------------------------------------------------------
# 2. 基础依赖（Python 3.11 / Node / MongoDB / Redis）
# -----------------------------------------------------------------------------
echo "==> 安装 Python 3.11 / Node.js / MongoDB / Redis（首次约需几分钟）..."
brew install python@3.11 node redis
brew tap mongodb/brew
brew install mongodb-community

# -----------------------------------------------------------------------------
# 3. 数据库服务（brew services 托管，开机自启）
# -----------------------------------------------------------------------------
echo "==> 启动 MongoDB / Redis 服务..."
brew services start mongodb-community
brew services start redis
sleep 3

# -----------------------------------------------------------------------------
# 4. 后端 Python 虚拟环境与依赖
# -----------------------------------------------------------------------------
if [ ! -d env ]; then
    echo "==> 创建 Python 3.11 虚拟环境 env/..."
    python3.11 -m venv env
fi
echo "==> 安装后端依赖（首次约需几分钟）..."
env/bin/python -m pip install --upgrade pip -q
env/bin/python -m pip install -r requirements.txt

# -----------------------------------------------------------------------------
# 5. 配置文件 .env
# -----------------------------------------------------------------------------
if [ ! -f .env ]; then
    echo "==> 生成 .env（本地学习默认配置）..."
    cp .env.example .env
    JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')
    ADMIN_PASSWORD=$(openssl rand -base64 12 | tr '/+' 'Aa')
    # 本地默认：MongoDB / Redis 无密码（brew 安装默认无认证）；生产环境请自行开启认证
    sed -i '' \
        -e "s|^MONGODB_CONNECTION_STRING=.*|MONGODB_CONNECTION_STRING=mongodb://localhost:27017/tradingagents|" \
        -e "s|^MONGODB_PASSWORD=.*|MONGODB_PASSWORD=|" \
        -e "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=|" \
        -e "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" \
        -e "s|^ADMIN_DEFAULT_PASSWORD=.*|ADMIN_DEFAULT_PASSWORD=${ADMIN_PASSWORD}|" \
        .env
    echo "    管理员账号 admin，初始密码: ${ADMIN_PASSWORD}（已写入 .env，登录后请修改）"
else
    echo "==> 已存在 .env，跳过配置生成"
fi

# -----------------------------------------------------------------------------
# 6. 前端构建
# -----------------------------------------------------------------------------
if [ ! -d frontend/dist ]; then
    echo "==> 安装前端依赖并构建（首次约需几分钟）..."
    (cd frontend && npm install && npm run build)
else
    echo "==> 前端已构建（frontend/dist 存在），跳过"
fi

echo ""
echo "=============================================="
echo "  安装完成！"
echo "  启动系统:      bash start.sh"
echo "  浏览器访问:    http://localhost:8000"
echo "  管理员账号:    admin（密码见 .env 的 ADMIN_DEFAULT_PASSWORD）"
echo "=============================================="
