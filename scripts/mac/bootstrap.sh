#!/usr/bin/env bash
# TradingAgents-CN Mac 部署脚本
# 在仓库根目录运行: bash scripts/mac/bootstrap.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INSTALL_DIR="${HOME}/Applications/TradingAgents-CN"
COMPOSE_FILE="docker-compose.hub.nginx.arm.yml"
DEFAULT_VERSION="$(tr -d '[:space:]' < "${REPO_ROOT}/VERSION" 2>/dev/null || echo "v1.0.1")"

red() { echo -e "\033[0;31m$*\033[0m"; }
green() { echo -e "\033[0;32m$*\033[0m"; }
cyan() { echo -e "\033[0;36m$*\033[0m"; }

echo ""
cyan "=========================================="
cyan " TradingAgents-CN Mac 部署向导"
cyan "=========================================="
echo ""

# 检查 Docker
if ! command -v docker >/dev/null 2>&1; then
  red "未找到 Docker，请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  cyan "正在启动 Docker Desktop..."
  open -a Docker
  for i in $(seq 1 60); do
    docker info >/dev/null 2>&1 && break
    sleep 2
  done
fi

if ! docker info >/dev/null 2>&1; then
  red "Docker 未就绪，请打开 Docker Desktop 后重新运行此脚本。"
  exit 1
fi

green "✓ Docker 已就绪"

mkdir -p "${INSTALL_DIR}/nginx" "${INSTALL_DIR}/logs" "${INSTALL_DIR}/data"

# 复制 compose / nginx
cp "${REPO_ROOT}/${COMPOSE_FILE}" "${INSTALL_DIR}/"
cp "${REPO_ROOT}/nginx/nginx.conf" "${INSTALL_DIR}/nginx/"

# 复制启动脚本
cp "${REPO_ROOT}/scripts/mac/start.command" "${INSTALL_DIR}/"
cp "${REPO_ROOT}/scripts/mac/update.sh" "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/start.command" "${INSTALL_DIR}/update.sh"

# 交互配置
echo ""
cyan "请输入 Docker Hub 用户名（你的 fork 发版镜像 namespace）:"
read -r DOCKERHUB_USER
DOCKERHUB_USER="${DOCKERHUB_USER:-YOUR_DOCKERHUB}"

echo ""
cyan "请输入 Gitee OTA manifest URL（发版后 CI 同步的地址）:"
cyan "示例: https://gitee.com/YOUR_USER/TradingAgents-OTA/raw/main/update-manifest.json"
read -r MANIFEST_URL
MANIFEST_URL="${MANIFEST_URL:-https://gitee.com/YOUR_USER/TradingAgents-OTA/raw/main/update-manifest.json}"

echo ""
cyan "请输入初始版本 tag（直接回车使用 ${DEFAULT_VERSION}）:"
read -r INIT_VERSION
INIT_VERSION="${INIT_VERSION:-${DEFAULT_VERSION}}"

# 生成 .env
if [[ -f "${INSTALL_DIR}/.env" ]]; then
  cyan "检测到已有 .env，保留现有配置，仅更新镜像与 OTA 变量..."
  ENV_TARGET="${INSTALL_DIR}/.env"
else
  if [[ -f "${REPO_ROOT}/.env.docker" ]]; then
    cp "${REPO_ROOT}/.env.docker" "${INSTALL_DIR}/.env"
  elif [[ -f "${REPO_ROOT}/.env.example" ]]; then
    cp "${REPO_ROOT}/.env.example" "${INSTALL_DIR}/.env"
  else
    touch "${INSTALL_DIR}/.env"
  fi
  ENV_TARGET="${INSTALL_DIR}/.env"
  echo ""
  cyan "请至少配置一个 AI 模型 API Key（编辑 ${ENV_TARGET}）"
  cyan "推荐: DEEPSEEK_API_KEY 或 DASHSCOPE_API_KEY，并设置对应 *_ENABLED=true"
  read -r -p "按回车继续（可稍后在 .env 中修改）..."
fi

append_or_replace() {
  local key="$1" val="$2" file="$3"
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    sed -i '' "s|^${key}=.*|${key}=${val}|" "$file"
  else
    echo "${key}=${val}" >> "$file"
  fi
}

append_or_replace "BACKEND_IMAGE" "${DOCKERHUB_USER}/tradingagents-backend:${INIT_VERSION}" "$ENV_TARGET"
append_or_replace "FRONTEND_IMAGE" "${DOCKERHUB_USER}/tradingagents-frontend:${INIT_VERSION}" "$ENV_TARGET"
append_or_replace "MANIFEST_URL" "${MANIFEST_URL}" "$ENV_TARGET"

echo "${INIT_VERSION}" > "${INSTALL_DIR}/VERSION"

# 桌面快捷方式
DESKTOP_LINK="${HOME}/Desktop/TradingAgents-CN.command"
cp "${INSTALL_DIR}/start.command" "${DESKTOP_LINK}"
chmod +x "${DESKTOP_LINK}"
green "✓ 已在桌面创建快捷方式: TradingAgents-CN.command"

echo ""
cyan "正在拉取镜像并启动（首次可能较慢）..."
cd "${INSTALL_DIR}"
docker compose -f "$COMPOSE_FILE" pull
docker compose -f "$COMPOSE_FILE" up -d

green ""
green "部署完成！"
green "  安装目录: ${INSTALL_DIR}"
green "  启动方式: 双击桌面「TradingAgents-CN.command」"
green "  访问地址: http://localhost"
green ""
green "发版后目标 Mac 会在启动时自动 OTA 更新（需配置 GitHub Secrets + Gitee）。"
echo ""
