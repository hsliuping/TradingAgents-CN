#!/bin/bash
# TradingAgents-CN Pro - Docker 构建时编译和清理脚本
# 
# 功能:
# 1. 编译 core/licensing/ 为 .so（Cython）
# 2. 编译 core/ 其他模块为 .pyc（字节码）
# 3. 编译 app/ 为 .pyc（字节码）
# 4. 清理源码，只保留必要的 .py 文件
# 5. tradingagents/ 保持源码（开源部分）
#
# 保留规则:
# - 所有 __init__.py（包导入需要）
# - 所有 __main__.py（入口文件）
# - core/licensing/models.py（数据模型，被其他模块导入）
# - tradingagents/ 所有源码（开源部分）
#
# 删除规则:
# - core/licensing/ 除 __init__.py 和 models.py 外的所有 .py
# - core/ 其他目录的所有 .py（除 __init__.py）
# - app/ 所有 .py（除 __init__.py 和 __main__.py）

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Docker Build - Compile and Cleanup${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 检查当前目录
if [ ! -d "core" ] || [ ! -d "app" ]; then
    echo -e "${RED}❌ Error: Must run from project root${NC}"
    exit 1
fi

# ============================================================================
# 步骤 1: 编译 core/licensing/ 为 .so（Cython）
# ============================================================================

echo -e "${BLUE}[1/5] Compiling core/licensing/ with Cython...${NC}"
echo ""

if [ -d "core/licensing" ]; then
    # 检查 Cython 是否安装
    if ! python -c "import Cython" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Cython not installed, installing...${NC}"
        pip install Cython
    fi
    
    # 创建临时 setup.py
    cat > /tmp/setup_licensing.py << 'EOF'
from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# 需要编译的文件
py_files = [
    'core/licensing/validator.py',
    'core/licensing/manager.py',
    'core/licensing/hardware.py',
    'core/licensing/crypto_utils.py',
]

# 创建扩展
extensions = [
    Extension(
        name=f.replace('/', '.').replace('.py', ''),
        sources=[f],
        extra_compile_args=['-O3'],
    )
    for f in py_files if os.path.exists(f)
]

setup(
    name='tradingagents-licensing',
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': '3',
            'embedsignature': False,
            'boundscheck': False,
            'wraparound': False,
        }
    ),
)
EOF
    
    # 编译
    echo -e "${GRAY}  Compiling...${NC}"
    python /tmp/setup_licensing.py build_ext --inplace
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✅ Cython compilation completed${NC}"
        
        # 删除源码（保留 __init__.py 和 models.py）
        echo -e "${GRAY}  Removing source files...${NC}"
        find core/licensing -name "*.py" \
            ! -name "__init__.py" \
            ! -name "models.py" \
            -type f -delete
        
        # 清理编译产物
        rm -f /tmp/setup_licensing.py
        rm -rf build/
        find core/licensing -name "*.c" -type f -delete
        
        echo -e "${GREEN}  ✅ Source files cleaned${NC}"
    else
        echo -e "${RED}  ❌ Cython compilation failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}  ⚠️  core/licensing not found, skipping${NC}"
fi

echo ""

# ============================================================================
# 步骤 2: 编译 core/ 其他模块为 .pyc
# ============================================================================

echo -e "${BLUE}[2/5] Compiling core/ to bytecode...${NC}"
echo ""

if [ -d "core" ]; then
    echo -e "${GRAY}  Compiling...${NC}"
    python -OO -m compileall -b core/
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✅ Bytecode compilation completed${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Bytecode compilation failed${NC}"
    fi
fi

echo ""

# ============================================================================
# 步骤 3: 编译 app/ 为 .pyc
# ============================================================================

echo -e "${BLUE}[3/5] Compiling app/ to bytecode...${NC}"
echo ""

if [ -d "app" ]; then
    echo -e "${GRAY}  Compiling...${NC}"
    python -OO -m compileall -b app/

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✅ Bytecode compilation completed${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Bytecode compilation failed${NC}"
    fi
fi

echo ""

# ============================================================================
# 步骤 4: 移动 .pyc 文件到正确位置
# ============================================================================

echo -e "${BLUE}[4/5] Moving .pyc files...${NC}"
echo ""

# 移动 core/ 的 .pyc 文件
if [ -d "core" ]; then
    find core -type d -name "__pycache__" | while read pycache_dir; do
        parent_dir=$(dirname "$pycache_dir")

        find "$pycache_dir" -name "*.pyc" | while read pyc_file; do
            filename=$(basename "$pyc_file")
            # 提取基础名称（去掉 .cpython-310.pyc 后缀）
            if [[ $filename =~ ^(.+)\.cpython-[0-9]+\.pyc$ ]]; then
                base_name="${BASH_REMATCH[1]}"
                new_name="${base_name}.pyc"
                mv "$pyc_file" "$parent_dir/$new_name"
            fi
        done

        # 删除 __pycache__ 目录
        rm -rf "$pycache_dir"
    done
    echo -e "${GREEN}  ✅ core/ .pyc files moved${NC}"
fi

# 移动 app/ 的 .pyc 文件
if [ -d "app" ]; then
    find app -type d -name "__pycache__" | while read pycache_dir; do
        parent_dir=$(dirname "$pycache_dir")

        find "$pycache_dir" -name "*.pyc" | while read pyc_file; do
            filename=$(basename "$pyc_file")
            if [[ $filename =~ ^(.+)\.cpython-[0-9]+\.pyc$ ]]; then
                base_name="${BASH_REMATCH[1]}"
                new_name="${base_name}.pyc"
                mv "$pyc_file" "$parent_dir/$new_name"
            fi
        done

        rm -rf "$pycache_dir"
    done
    echo -e "${GREEN}  ✅ app/ .pyc files moved${NC}"
fi

echo ""

# ============================================================================
# 步骤 5: 清理源码文件
# ============================================================================

echo -e "${BLUE}[5/5] Cleaning up source files...${NC}"
echo ""

# 清理 core/ 源码（保留 __init__.py 和 licensing/models.py）
if [ -d "core" ]; then
    echo -e "${GRAY}  Cleaning core/ source files...${NC}"

    # 使用数组收集要删除的文件
    files_to_delete=()

    while IFS= read -r py_file; do
        filename=$(basename "$py_file")

        # 检查是否是 licensing/models.py
        if [[ "$py_file" == "core/licensing/models.py" ]]; then
            continue
        fi

        # 保留 __init__.py
        if [ "$filename" != "__init__.py" ]; then
            # 检查是否有对应的 .pyc 或 .so
            dir=$(dirname "$py_file")
            base=$(basename "$py_file" .py)

            if [ -f "$dir/$base.pyc" ] || [ -f "$dir/$base.so" ] || compgen -G "$dir/$base.*.so" > /dev/null; then
                files_to_delete+=("$py_file")
            fi
        fi
    done < <(find core -name "*.py" -type f)

    # 删除文件
    for file in "${files_to_delete[@]}"; do
        echo -e "${GRAY}    Removing: $file${NC}"
        rm -f "$file"
    done

    echo -e "${GREEN}  ✅ Removed ${#files_to_delete[@]} core/ source files${NC}"
fi

# 清理 app/ 源码（保留 __init__.py 和 __main__.py）
if [ -d "app" ]; then
    echo -e "${GRAY}  Cleaning app/ source files...${NC}"

    # 使用数组收集要删除的文件
    files_to_delete=()

    while IFS= read -r py_file; do
        filename=$(basename "$py_file")

        # 保留 __init__.py 和 __main__.py
        if [ "$filename" != "__init__.py" ] && [ "$filename" != "__main__.py" ]; then
            # 检查是否有对应的 .pyc
            dir=$(dirname "$py_file")
            base=$(basename "$py_file" .py)

            if [ -f "$dir/$base.pyc" ]; then
                files_to_delete+=("$py_file")
            fi
        fi
    done < <(find app -name "*.py" -type f)

    # 删除文件
    for file in "${files_to_delete[@]}"; do
        echo -e "${GRAY}    Removing: $file${NC}"
        rm -f "$file"
    done

    echo -e "${GREEN}  ✅ Removed ${#files_to_delete[@]} app/ source files${NC}"
fi

# 验证 tradingagents/ 保持源码
if [ -d "tradingagents" ]; then
    echo -e "${GREEN}  ✅ tradingagents/ source code preserved (open source)${NC}"
fi

echo ""

# ============================================================================
# 完成
# ============================================================================

echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}✅ Compilation and cleanup completed!${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

echo -e "${GREEN}Summary:${NC}"
echo -e "  - core/licensing/    → ${YELLOW}.so files (Cython)${NC}"
echo -e "  - core/other/        → ${YELLOW}.pyc files (bytecode)${NC}"
echo -e "  - app/               → ${YELLOW}.pyc files (bytecode)${NC}"
echo -e "  - tradingagents/     → ${YELLOW}.py files (source code)${NC}"
echo ""

echo -e "${GREEN}Preserved files:${NC}"
echo -e "  - All ${YELLOW}__init__.py${NC}"
echo -e "  - All ${YELLOW}__main__.py${NC}"
echo -e "  - ${YELLOW}core/licensing/models.py${NC}"
echo ""

