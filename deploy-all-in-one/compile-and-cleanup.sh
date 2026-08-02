#!/bin/bash
# TradingAgents-CN Pro v3.0 - Docker 构建时编译和清理脚本
#
# 功能:
# 1. 编译 app/ 为 .pyc（字节码）
# 2. 编译 core/ 为 .pyc（字节码）
# 3. 清理源码，只保留必要的 .py 文件
# 4. tradingagents/ 保持源码（开源部分）
#
# 与 v2.0 docker/scripts/compile-and-cleanup.sh 的区别:
#   - 不做 Cython 编译（京东云版已禁用 License，无需保护 licensing 逻辑）
#   - 简化为纯字节码编译，兼容性更好
#
# 保留规则:
# - 所有 __init__.py（包导入需要）
# - 所有 __main__.py（入口文件）
# - tradingagents/ 所有源码（开源部分）
# - config/ scripts/ 不编译（运行时配置需要）
#
# 删除规则:
# - app/ 所有 .py（除 __init__.py 和 __main__.py，已编译为 .pyc）
# - core/ 所有 .py（除 __init__.py，已编译为 .pyc）

set -e

echo "========================================"
echo "  Python 代码编译和源码清理"
echo "========================================"
echo ""

# 检查当前目录
if [ ! -d "core" ] || [ ! -d "app" ]; then
    echo "❌ 错误: 必须在项目根目录执行（需包含 app/ 和 core/）"
    exit 1
fi

# ============================================================================
# 步骤 1: 编译 app/ 为 .pyc
# ============================================================================
echo "[1/4] 编译 app/ 为字节码..."
python -m compileall -b app/ 2>&1 | grep -v "^Listing" || true
echo "✅ app/ 编译完成"
echo ""

# ============================================================================
# 步骤 2: 编译 core/ 为 .pyc
# ============================================================================
echo "[2/4] 编译 core/ 为字节码..."
python -m compileall -b core/ 2>&1 | grep -v "^Listing" || true
echo "✅ core/ 编译完成"
echo ""

# ============================================================================
# 步骤 3: 移动 .pyc 文件到正确位置并清理 __pycache__
# ============================================================================
echo "[3/4] 整理 .pyc 文件..."

# 移动 app/ 的 .pyc 文件
find app -type d -name "__pycache__" | while read pycache_dir; do
    parent_dir=$(dirname "$pycache_dir")
    find "$pycache_dir" -name "*.pyc" | while read pyc_file; do
        filename=$(basename "$pyc_file")
        # 提取基础名称（去掉 .cpython-311.pyc 后缀）
        if [[ $filename =~ ^(.+)\.cpython-[0-9]+\.pyc$ ]]; then
            base_name="${BASH_REMATCH[1]}"
            new_name="${base_name}.pyc"
            mv "$pyc_file" "$parent_dir/$new_name"
        fi
    done
    rm -rf "$pycache_dir"
done
echo "✅ app/ .pyc 文件整理完成"

# 移动 core/ 的 .pyc 文件
find core -type d -name "__pycache__" | while read pycache_dir; do
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
echo "✅ core/ .pyc 文件整理完成"
echo ""

# ============================================================================
# 步骤 4: 清理源码文件
# ============================================================================
echo "[4/4] 清理源码文件..."

# 清理 app/ 源码（保留 __init__.py 和 __main__.py）
app_py_count=0
while IFS= read -r py_file; do
    filename=$(basename "$py_file")
    if [ "$filename" != "__init__.py" ] && [ "$filename" != "__main__.py" ]; then
        dir=$(dirname "$py_file")
        base=$(basename "$py_file" .py)
        # 只在有对应 .pyc 的情况下删除源码
        if [ -f "$dir/$base.pyc" ]; then
            rm -f "$py_file"
            app_py_count=$((app_py_count + 1))
        fi
    fi
done < <(find app -name "*.py" -type f)
echo "✅ app/ 删除 $app_py_count 个源码文件"

# 清理 core/ 源码（保留 __init__.py）
core_py_count=0
while IFS= read -r py_file; do
    filename=$(basename "$py_file")
    if [ "$filename" != "__init__.py" ]; then
        dir=$(dirname "$py_file")
        base=$(basename "$py_file" .py)
        # 只在有对应 .pyc 的情况下删除源码
        if [ -f "$dir/$base.pyc" ]; then
            rm -f "$py_file"
            core_py_count=$((core_py_count + 1))
        fi
    fi
done < <(find core -name "*.py" -type f)
echo "✅ core/ 删除 $core_py_count 个源码文件"

# tradingagents/ 保留源码（开源部分）
echo "✅ tradingagents/ 源码保留（开源部分）"
echo ""

# ============================================================================
# 统计信息
# ============================================================================
echo "========================================"
echo "  编译完成统计"
echo "========================================"

APP_PYC=$(find app -name "*.pyc" -type f | wc -l)
APP_PY=$(find app -name "*.py" -type f | wc -l)
CORE_PYC=$(find core -name "*.pyc" -type f | wc -l)
CORE_PY=$(find core -name "*.py" -type f | wc -l)
TA_PY=$(find tradingagents -name "*.py" -type f | wc -l 2>/dev/null || echo 0)

echo "  app/:            $APP_PYC 个 .pyc, $APP_PY 个 .py（保留 __init__/__main__）"
echo "  core/:           $CORE_PYC 个 .pyc, $CORE_PY 个 .py（保留 __init__）"
echo "  tradingagents/:  $TA_PY 个 .py（开源源码保留）"
echo ""
echo "✅ 编译和清理完成！"
