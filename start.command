#!/bin/bash
# ============================================================================
# AITrading 桌面应用启动脚本
# 1. 检查并释放 8100 端口
# 2. 启动后端服务（python -m app）
# 3. 检查并关闭已有的 AITrading.app
# 4. 启动 AITrading.app
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m'

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}      AITrading 桌面应用 - 一键启动脚本${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

BACKEND_PORT=${BACKEND_PORT:-8100}
BACKEND_URL="http://localhost:${BACKEND_PORT}/api/health"
APP_PATH="/Applications/AITrading.app"
ALT_APP_PATH="$PROJECT_ROOT/app-desktop/release/mac-arm64/AITrading.app"

# ========================================================================
# 1. 检查并释放 8100 端口
# ========================================================================
echo -e "${YELLOW}[1/4] 检查 8100 端口占用...${NC}"
PORT_PID=$(lsof -ti :${BACKEND_PORT} 2>/dev/null)
if [ -n "$PORT_PID" ]; then
  echo -e "${YELLOW}  ⚠️  端口 ${BACKEND_PORT} 被 PID ${PORT_PID} 占用，正在关闭...${NC}"
  kill -9 $PORT_PID 2>/dev/null || true
  sleep 1
  # 再次确认端口已释放
  if lsof -ti :${BACKEND_PORT} > /dev/null 2>&1; then
    echo -e "${RED}  ❌ 无法释放端口 ${BACKEND_PORT}，请手动关闭占用程序${NC}"
    exit 1
  fi
  echo -e "${GREEN}  ✅ 端口 ${BACKEND_PORT} 已释放${NC}"
else
  echo -e "${GREEN}  ✅ 端口 ${BACKEND_PORT} 未被占用${NC}"
fi
echo ""

# ========================================================================
# 2. 启动后端服务
# ========================================================================
echo -e "${YELLOW}[2/4] 启动后端服务...${NC}"

cd "$PROJECT_ROOT"
mkdir -p logs
# 使用 nohup 避免终端关闭后 stdout/stderr 管道破裂
export LOGURU_LEVEL="INFO"
nohup python -m app > logs/app_output.log 2>&1 &
BACKEND_PID=$!
echo -e "${GRAY}  后端 PID: ${BACKEND_PID}${NC}"
echo -e "${GRAY}  后端日志输出到: logs/app_output.log${NC}"
echo ""

# 等待后端就绪
echo -e "${YELLOW}[3/4] 等待后端服务就绪...${NC}"
MAX_RETRIES=60
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if curl -s "$BACKEND_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}  ✅ 后端服务已就绪 (端口 ${BACKEND_PORT})${NC}"
    break
  fi
  RETRY_COUNT=$((RETRY_COUNT + 1))
  printf "${GRAY}  .${NC}"
  sleep 2
done
echo ""

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
  echo -e "${RED}❌ 后端服务启动超时（${MAX_RETRIES} 次重试），请检查上方日志${NC}"
  kill $BACKEND_PID 2>/dev/null || true
  exit 1
fi
echo ""

# ========================================================================
# 3. 检查并关闭已有的 AITrading.app
# ========================================================================
echo -e "${YELLOW}[4/4] 启动 AITrading.app...${NC}"

if pgrep -f "AITrading.app/Contents/MacOS/AITrading" > /dev/null 2>&1; then
  echo -e "${YELLOW}  ⚠️  AITrading.app 已在运行，正在关闭...${NC}"
  pkill -f "AITrading.app/Contents/MacOS/AITrading" 2>/dev/null || true
  sleep 2
  echo -e "${GREEN}  ✅ 旧 AITrading.app 已关闭${NC}"
fi

# ========================================================================
# 4. 启动 AITrading.app
# ========================================================================
if [ -d "$APP_PATH" ]; then
  open "$APP_PATH"
  echo -e "${GREEN}  ✅ AITrading.app 已启动${NC}"
elif [ -d "$ALT_APP_PATH" ]; then
  open "$ALT_APP_PATH"
  echo -e "${GREEN}  ✅ AITrading.app (开发版) 已启动${NC}"
else
  echo -e "${RED}  ❌ 找不到 AITrading.app，请先安装或构建${NC}"
  echo -e "${RED}     查找路径: ${APP_PATH}${NC}"
  echo -e "${RED}     备选路径: ${ALT_APP_PATH}${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}              启动完成！${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  后端地址: ${CYAN}http://localhost:${BACKEND_PORT}${NC}"
echo -e "  API 文档: ${CYAN}http://localhost:${BACKEND_PORT}/docs${NC}"
echo ""
