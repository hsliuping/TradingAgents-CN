#!/bin/bash
# TradingAgents-CN Pro - Python 代码编译脚本
# 将 Python 源码编译为 .pyc 字节码文件
# 
# 功能:
# 1. 编译 app/ 和 core/ 为 .pyc（除了 core/licensing）
# 2. core/licensing 使用 Cython 编译为 .pyd（如果安装了 Cython）
# 3. tradingagents/ 保留源码（开源部分）
#
# 使用方法:
#   ./docker/scripts/compile-code.sh

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPILE_DIR="$PROJECT_ROOT/docker/build/compiled"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Python 代码编译${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}📋 配置:${NC}"
echo -e "  项目根目录: ${YELLOW}$PROJECT_ROOT${NC}"
echo -e "  编译输出目录: ${YELLOW}$COMPILE_DIR${NC}"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 错误: 未找到 python3${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✅ Python 版本: ${YELLOW}$PYTHON_VERSION${NC}"
echo ""

# 清理旧的编译目录
if [ -d "$COMPILE_DIR" ]; then
    echo -e "${YELLOW}🧹 清理旧的编译目录...${NC}"
    rm -rf "$COMPILE_DIR"
fi

# 创建编译目录
mkdir -p "$COMPILE_DIR"

# 步骤 1: 复制源代码
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 1: 复制源代码${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${GREEN}📦 复制 app/ 目录...${NC}"
cp -r "$PROJECT_ROOT/app" "$COMPILE_DIR/"

echo -e "${GREEN}📦 复制 core/ 目录...${NC}"
cp -r "$PROJECT_ROOT/core" "$COMPILE_DIR/"

echo -e "${GREEN}📦 复制 tradingagents/ 目录...${NC}"
cp -r "$PROJECT_ROOT/tradingagents" "$COMPILE_DIR/"

echo -e "${GREEN}✅ 源代码复制完成${NC}"
echo ""

# 步骤 2: 编译 Python 代码
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 2: 编译 Python 代码${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 编译 app/ 目录
echo -e "${GREEN}🔧 编译 app/ 目录...${NC}"
python3 -m compileall -b "$COMPILE_DIR/app" 2>&1 | grep -v "^Listing" || true

# 编译 core/ 目录（排除 licensing）
echo -e "${GREEN}🔧 编译 core/ 目录（排除 licensing）...${NC}"
python3 -m compileall -b "$COMPILE_DIR/core" -x "licensing" 2>&1 | grep -v "^Listing" || true

echo -e "${GREEN}✅ 编译完成${NC}"
echo ""

# 步骤 3: 删除源码 .py 文件
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 3: 删除源码文件${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${GREEN}🗑️  删除 app/ 中的 .py 文件（保留 __init__.py）...${NC}"
find "$COMPILE_DIR/app" -type f -name "*.py" ! -name "__init__.py" -delete

echo -e "${GREEN}🗑️  删除 core/ 中的 .py 文件（保留 __init__.py 和 licensing/）...${NC}"
find "$COMPILE_DIR/core" -type f -name "*.py" ! -name "__init__.py" ! -path "*/licensing/*" -delete

echo -e "${GREEN}✅ 源码文件删除完成${NC}"
echo ""

# 步骤 4: 处理 core/licensing（可选 Cython 编译）
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 4: 处理 core/licensing${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if command -v cython &> /dev/null; then
    echo -e "${GREEN}🔐 检测到 Cython，可以进行高级编译${NC}"
    echo -e "${YELLOW}⚠️  Cython 编译需要额外配置，当前保留源码${NC}"
    echo -e "${YELLOW}⚠️  如需 Cython 编译，请参考文档手动配置${NC}"
else
    echo -e "${YELLOW}⚠️  未安装 Cython，core/licensing 保留源码${NC}"
    echo -e "${YELLOW}提示: 安装 Cython: pip install cython${NC}"
fi
echo ""

# 步骤 5: tradingagents 保留源码
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 5: tradingagents 保留源码${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}✅ tradingagents/ 保留源码（开源部分）${NC}"
echo ""

# 统计信息
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}编译统计${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

PYC_COUNT=$(find "$COMPILE_DIR" -name "*.pyc" | wc -l)
PY_COUNT=$(find "$COMPILE_DIR" -name "*.py" | wc -l)

echo -e "${GREEN}  .pyc 文件数量: ${YELLOW}$PYC_COUNT${NC}"
echo -e "${GREEN}  .py 文件数量: ${YELLOW}$PY_COUNT${NC}"
echo -e "${GREEN}  编译输出目录: ${YELLOW}$COMPILE_DIR${NC}"
echo ""

echo -e "${GREEN}✅ 编译完成！${NC}"
echo ""
echo -e "${GREEN}下一步:${NC}"
echo -e "  构建 Docker 镜像:"
echo -e "  ${YELLOW}./docker/scripts/build-compile.sh${NC}"

