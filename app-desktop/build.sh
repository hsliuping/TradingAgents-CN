#!/bin/bash
# ============================================================================
# AITrading Electron 打包脚本（macOS / Linux）
#
# 用法：
#   ./build.sh              - 完整打包（构建前端 + 复制dist + 打包DMG）
#   ./build.sh -q           - 快速打包（跳过前端构建）
#   ./build.sh -d           - 开发模式
#   ./build.sh -c           - 清理后重新打包
#
# 输出：
#   release/AITrading-1.0.0-mac.dmg（macOS 独立可执行文件）
# ============================================================================

set -euo pipefail

# ---------- 参数解析 ----------
QUICK=false
DEV=false
CLEAN=false

while getopts "qdc" opt; do
  case $opt in
    q) QUICK=true ;;
    d) DEV=true ;;
    c) CLEAN=true ;;
    *) echo "用法: $0 [-q] [-d] [-c]"; exit 1 ;;
  esac
done

# ---------- 路径 ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$ROOT_DIR/frontend"
ELECTRON_DIR="$SCRIPT_DIR"

# ---------- 颜色输出 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}         AITrading Electron 打包脚本 v1.0.0 (macOS)${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# ---------- 平台检测 ----------
OS="$(uname -s)"
case "$OS" in
  Darwin)  echo -e "${GREEN}  运行平台: macOS${NC}" ;;
  Linux)   echo -e "${YELLOW}  运行平台: Linux（将构建 macOS 目标，可能受限）${NC}" ;;
  *)       echo -e "${RED}[错误] 此脚本仅支持 macOS / Linux${NC}"; exit 1 ;;
esac
echo ""

# ---------- 清理 ----------
if $CLEAN; then
  echo -e "${YELLOW}[清理] 删除旧的构建产物...${NC}"
  for p in "$FRONTEND_DIR/dist" "$ELECTRON_DIR/dist" "$ELECTRON_DIR/release"; do
    if [ -d "$p" ]; then
      rm -rf "$p"
      echo "  - $p"
    fi
  done
  echo ""
fi

# ---------- 开发模式 ----------
if $DEV; then
  echo -e "${GREEN}>>> 开发模式：启动 Electron + Vite 开发服务器${NC}"
  echo ""

  echo -e "${CYAN}[启动] Vite 开发服务器 (端口 3000)...${NC}"
  (cd "$FRONTEND_DIR" && npx vite --host 0.0.0.0 --port 3000) &
  VITE_PID=$!
  echo "  Vite PID: $VITE_PID"

  echo -e "${CYAN}[等待] 等待 Vite 开发服务器就绪...${NC}"
  for i in $(seq 1 30); do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  echo -e "${GREEN}  Vite 已就绪!${NC}"

  echo -e "${CYAN}[启动] Electron...${NC}"
  (cd "$ELECTRON_DIR" && npx electron .)
  kill $VITE_PID 2>/dev/null || true
  exit 0
fi

# ---------- 步骤 1：构建前端 ----------
if ! $QUICK; then
  echo -e "${YELLOW}[1/4] 构建 Vue 前端项目...${NC}"
  cd "$FRONTEND_DIR"
  # Electron 生产环境通过 file:// 加载页面，需要指定后端 API 地址
  export VITE_API_BASE_URL=http://localhost:8100
  npx vite build
  if [ $? -ne 0 ]; then
    echo -e "${RED}[错误] 前端构建失败${NC}"
    exit 1
  fi
  echo -e "${GREEN}  前端构建完成!${NC}"
  echo ""
else
  echo -e "${YELLOW}[1/4] 快速模式：跳过前端构建${NC}"
  if [ ! -d "$FRONTEND_DIR/dist" ]; then
    echo -e "${RED}[错误] 找不到 frontend/dist，请先构建前端${NC}"
    exit 1
  fi
  echo ""
fi

# ---------- 步骤 2：复制前端产物 ----------
echo -e "${YELLOW}[2/4] 复制前端构建产物到 app-desktop/dist...${NC}"
SRC_DIST="$FRONTEND_DIR/dist"
DST_DIST="$ELECTRON_DIR/dist"
if [ -d "$DST_DIST" ]; then
  rm -rf "$DST_DIST"
fi
cp -R "$SRC_DIST" "$DST_DIST"
echo -e "${GREEN}  复制完成: $DST_DIST${NC}"
FILE_COUNT=$(find "$DST_DIST" -type f | wc -l | tr -d ' ')
echo -e "${GRAY}  文件数: $FILE_COUNT${NC}"
echo ""

# ---------- 步骤 3：安装依赖 ----------
echo -e "${YELLOW}[3/4] 检查 Electron 依赖...${NC}"
cd "$ELECTRON_DIR"
if [ ! -f "node_modules/.package-lock.json" ]; then
  echo -e "${GRAY}  正在安装依赖...${NC}"
  npm install
  if [ $? -ne 0 ]; then
    echo -e "${RED}[错误] 依赖安装失败${NC}"
    exit 1
  fi
  echo -e "${GREEN}  依赖安装完成!${NC}"
else
  echo -e "${GREEN}  依赖已存在，跳过${NC}"
fi
echo ""

# ---------- 步骤 4：打包 ----------
echo -e "${YELLOW}[4/4] 打包 Electron 应用（macOS DMG）...${NC}"
echo -e "${GRAY}  目标: .dmg 文件${NC}"
echo ""

# 跳过代码签名（本地打包无需 Apple Developer 证书）
export CSC_IDENTITY_AUTO_DISCOVERY=false

# 临时修改 package.json，只构建 arm64 避免双架构冲突
echo -e "${GRAY}  临时修改 package.json, 仅构建 arm64...${NC}"
cp package.json package.json.bak
node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
if (pkg.build && pkg.build.mac && pkg.build.mac.target && pkg.build.mac.target[0].arch) {
  pkg.build.mac.target[0].arch = ['arm64'];
}
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
"

npx electron-builder --mac --arm64
BUILD_EXIT_CODE=$?

# 恢复 package.json 原始配置
mv package.json.bak package.json
echo -e "${GRAY}  已恢复 package.json 原始配置${NC}"

if [ $BUILD_EXIT_CODE -ne 0 ]; then
  echo -e "${RED}[错误] 打包失败${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}           打包完成！${NC}"
echo -e "${GREEN}============================================================${NC}"

RELEASE_DIR="$ELECTRON_DIR/release"
if [ -d "$RELEASE_DIR" ]; then
  echo ""
  echo -e "${CYAN}  输出目录: $RELEASE_DIR${NC}"
  echo ""
  # 列出 DMG 文件
  find "$RELEASE_DIR" -name "*.dmg" -exec ls -lh {} \; 2>/dev/null || true
  # 列出 .app 文件
  find "$RELEASE_DIR" -name "*.app" -maxdepth 3 -exec echo "  App: {}" \; 2>/dev/null || true
  echo ""
  echo -e "${CYAN}  使用方法：${NC}"
  echo -e "    1. 双击 .dmg 文件挂载"
  echo -e "    2. 将 AITrading.app 拖入 Applications 文件夹"
  echo -e "    3. 首次打开如提示"未验证开发者"，前往 系统设置→隐私与安全性→仍要打开"
  echo ""
fi
