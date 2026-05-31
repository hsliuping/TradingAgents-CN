#!/usr/bin/env bash
# TradingAgents-CN Mac 启动脚本

set -euo pipefail

INSTALL_DIR="${HOME}/Applications/TradingAgents-CN"
COMPOSE_FILE="docker-compose.hub.nginx.arm.yml"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 若从仓库 scripts/mac 直接运行，则使用安装目录逻辑
if [[ -f "${SCRIPT_DIR}/update.sh" && "$SCRIPT_DIR" != "$INSTALL_DIR" ]]; then
  export INSTALL_DIR
fi

cd "${INSTALL_DIR}"

echo "正在启动 TradingAgents-CN..."

# 确保 Docker Desktop 运行
if ! docker info >/dev/null 2>&1; then
  echo "正在启动 Docker Desktop..."
  open -a Docker
  for i in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  if ! docker info >/dev/null 2>&1; then
    echo "Docker 未就绪，请手动打开 Docker Desktop 后重试。"
    read -r -p "按回车键退出..."
    exit 1
  fi
fi

# 静默检查 OTA（失败不阻塞启动）
if [[ -x "${INSTALL_DIR}/update.sh" ]]; then
  bash "${INSTALL_DIR}/update.sh" --check || true
elif [[ -x "${SCRIPT_DIR}/update.sh" ]]; then
  bash "${SCRIPT_DIR}/update.sh" --check || true
fi

echo "正在启动服务..."
docker compose -f "$COMPOSE_FILE" up -d

echo "等待服务就绪..."
for i in $(seq 1 40); do
  if curl -sf "http://localhost/api/health" | grep -qE '"status"[[:space:]]*:[[:space:]]*"ok"'; then
    echo "服务已就绪，正在打开浏览器..."
    open "http://localhost"
    exit 0
  fi
  sleep 3
done

echo "服务启动超时，请稍后访问 http://localhost"
open "http://localhost" || true
read -r -p "按回车键退出..."
