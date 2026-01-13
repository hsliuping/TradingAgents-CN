#!/bin/bash
# TradingAgents-CN Pro - Cython 编译脚本
# 将 core/licensing 目录编译为 .so 文件（Linux）或 .pyd 文件（Windows）
#
# 功能:
# 1. 检查 Cython 和编译工具
# 2. 为 core/licensing 中的每个 .py 文件生成 .pyx 文件
# 3. 使用 Cython 编译为 C 代码
# 4. 编译 C 代码为 .so 共享库
# 5. 删除源码 .py 文件
#
# 使用方法:
#   ./docker/scripts/compile-licensing.sh

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
LICENSING_DIR="$COMPILE_DIR/core/licensing"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Cython 编译 core/licensing${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查编译目录是否存在
if [ ! -d "$COMPILE_DIR" ]; then
    echo -e "${RED}❌ 错误: 编译目录不存在: $COMPILE_DIR${NC}"
    echo -e "${YELLOW}请先运行: ./docker/scripts/compile-code.sh${NC}"
    exit 1
fi

if [ ! -d "$LICENSING_DIR" ]; then
    echo -e "${RED}❌ 错误: licensing 目录不存在: $LICENSING_DIR${NC}"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 错误: 未找到 python3${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✅ Python 版本: ${YELLOW}$PYTHON_VERSION${NC}"

# 检查 Cython
if ! python3 -c "import Cython" 2>/dev/null; then
    echo -e "${RED}❌ 错误: 未安装 Cython${NC}"
    echo -e "${YELLOW}安装命令: pip3 install cython${NC}"
    exit 1
fi

CYTHON_VERSION=$(python3 -c "import Cython; print(Cython.__version__)")
echo -e "${GREEN}✅ Cython 版本: ${YELLOW}$CYTHON_VERSION${NC}"

# 检查编译工具
if ! command -v gcc &> /dev/null; then
    echo -e "${RED}❌ 错误: 未找到 gcc 编译器${NC}"
    echo -e "${YELLOW}安装命令: sudo apt-get install build-essential${NC}"
    exit 1
fi

GCC_VERSION=$(gcc --version | head -n1)
echo -e "${GREEN}✅ GCC 版本: ${YELLOW}$GCC_VERSION${NC}"

# 检查 Python 开发头文件
PYTHON_INCLUDE=$(python3 -c "from sysconfig import get_paths; print(get_paths()['include'])")
if [ ! -f "$PYTHON_INCLUDE/Python.h" ]; then
    echo -e "${RED}❌ 错误: 未找到 Python 开发头文件${NC}"
    echo -e "${YELLOW}安装命令: sudo apt-get install python3-dev${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 开发头文件: ${YELLOW}$PYTHON_INCLUDE${NC}"
echo ""

# 创建 setup.py 文件
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 1: 创建 setup.py${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

SETUP_FILE="$COMPILE_DIR/setup_licensing.py"

cat > "$SETUP_FILE" << 'EOF'
from setuptools import setup, Extension
from Cython.Build import cythonize
import os
import glob

# 获取 core/licensing 目录下所有 .py 文件（排除 __init__.py）
licensing_dir = "core/licensing"
py_files = []

for root, dirs, files in os.walk(licensing_dir):
    for file in files:
        if file.endswith('.py') and file != '__init__.py':
            py_path = os.path.join(root, file)
            py_files.append(py_path)

print(f"找到 {len(py_files)} 个 Python 文件需要编译:")
for f in py_files:
    print(f"  - {f}")

# 创建 Extension 列表
extensions = []
for py_file in py_files:
    # 将路径转换为模块名
    # 例如: core/licensing/validator.py -> core.licensing.validator
    module_name = py_file.replace('/', '.').replace('\\', '.').replace('.py', '')
    
    extensions.append(
        Extension(
            module_name,
            [py_file],
            extra_compile_args=['-O3'],  # 优化级别
        )
    )

setup(
    name='tradingagents-licensing',
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': '3',
            'embedsignature': True,
            'boundscheck': False,
            'wraparound': False,
        }
    ),
)
EOF

echo -e "${GREEN}✅ setup.py 创建完成${NC}"
echo ""

# 编译
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 2: Cython 编译${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

cd "$COMPILE_DIR"

echo -e "${GREEN}🔧 开始编译...${NC}"
python3 setup_licensing.py build_ext --inplace

echo -e "${GREEN}✅ 编译完成${NC}"
echo ""

# 删除源码和临时文件
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}步骤 3: 清理文件${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${GREEN}🗑️  删除 core/licensing 中的 .py 文件（保留 __init__.py）...${NC}"
find "$LICENSING_DIR" -type f -name "*.py" ! -name "__init__.py" -delete

echo -e "${GREEN}🗑️  删除 .c 临时文件...${NC}"
find "$LICENSING_DIR" -type f -name "*.c" -delete

echo -e "${GREEN}🗑️  删除 setup.py...${NC}"
rm -f "$SETUP_FILE"

echo -e "${GREEN}✅ 清理完成${NC}"
echo ""

# 统计
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}编译统计${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

SO_COUNT=$(find "$LICENSING_DIR" -name "*.so" | wc -l)
PY_COUNT=$(find "$LICENSING_DIR" -name "*.py" | wc -l)

echo -e "${GREEN}  .so 文件数量: ${YELLOW}$SO_COUNT${NC}"
echo -e "${GREEN}  .py 文件数量: ${YELLOW}$PY_COUNT${NC} (应该只有 __init__.py)"
echo ""

if [ $SO_COUNT -gt 0 ]; then
    echo -e "${GREEN}✅ Cython 编译成功！${NC}"
    echo ""
    echo -e "${GREEN}编译产物:${NC}"
    find "$LICENSING_DIR" -name "*.so" -exec ls -lh {} \;
else
    echo -e "${RED}❌ 错误: 未生成 .so 文件${NC}"
    exit 1
fi

