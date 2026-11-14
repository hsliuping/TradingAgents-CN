#!/usr/bin/env bash
# =============================================================================
# TradingAgents-CN macOS 启动脚本（社区版）
#
# 用途：启动后端（后端直接伺服前端页面，单端口部署），并自动打开浏览器
# 前置：已运行 bash install-mac.sh 完成安装
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# -----------------------------------------------------------------------------
# 前置检查
# -----------------------------------------------------------------------------
if [ ! -f .env ]; then
    echo "❌ 未找到 .env，请先运行一键安装：bash install-mac.sh"
    exit 1
fi
if [ ! -x env/bin/python ]; then
    echo "❌ 未找到 Python 虚拟环境 env/，请先运行一键安装：bash install-mac.sh"
    exit 1
fi

# -----------------------------------------------------------------------------
# 数据库服务自检（brew services 托管，未启动则拉起）
# -----------------------------------------------------------------------------
if ! redis-cli ping >/dev/null 2>&1; then
    echo "==> Redis 未响应，启动服务..."
    brew services start redis || true
    sleep 2
fi
if ! (exec 3<>/dev/tcp/127.0.0.1/27017) 2>/dev/null; then
    echo "==> MongoDB 未响应，启动服务..."
    brew services start mongodb-community || true
    sleep 5
fi

# -----------------------------------------------------------------------------
# 前端缺失时自动构建（正常只发生一次）
# -----------------------------------------------------------------------------
if [ ! -f frontend/dist/index.html ]; then
    echo "==> 未检测到前端构建产物，自动构建（约需几分钟）..."
    (cd frontend && npm install && npm run build)
fi

# -----------------------------------------------------------------------------
# 启动后端并打开浏览器
# -----------------------------------------------------------------------------
echo "==> 启动 TradingAgents-CN: http://localhost:8000 （Ctrl+C 停止）"

# 轮询后端就绪后自动打开浏览器（后台子进程，随主进程退出）
(
    for _ in $(seq 1 60); do
        if curl -sf http://localhost:8000/ >/dev/null 2>&1; then
            open "http://localhost:8000" 2>/dev/null || true
            break
        fi
        sleep 1
    done
) &

env/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
