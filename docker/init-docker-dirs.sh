#!/bin/bash
# ============================================================================
# Docker 目录初始化脚本 (Bash)
# ============================================================================
# 用途：创建 docker-compose.compiled.yml 需要的本地目录
# 
# 使用方法：
#   cd docker
#   chmod +x init-docker-dirs.sh
#   ./init-docker-dirs.sh
# ============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# 打印标题
echo -e "${CYAN}"
echo "========================================"
echo "  Docker 目录初始化"
echo "========================================"
echo -e "${NC}"

# 获取当前目录
current_dir=$(pwd)
echo -e "${GRAY}📁 当前目录: $current_dir${NC}"

# 检查是否在 docker 目录下
if [ ! -f "docker-compose.compiled.yml" ]; then
    echo -e "${RED}"
    echo "❌ 错误：请在 docker 目录下运行此脚本"
    echo -e "${YELLOW}   cd docker"
    echo "   ./init-docker-dirs.sh"
    echo -e "${NC}"
    exit 1
fi

# 需要创建的目录列表
directories=(
    "logs"
    "data"
    "runtime"
    "nginx"
)

echo -e "${YELLOW}"
echo "📂 创建必需的目录..."
echo -e "${NC}"

created_count=0
existing_count=0

for dir in "${directories[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo -e "${GREEN}  ✅ 创建目录: $dir${NC}"
        ((created_count++))
    else
        echo -e "${GRAY}  📁 目录已存在: $dir${NC}"
        ((existing_count++))
    fi
done

echo -e "${CYAN}"
echo "📊 统计信息:"
echo -e "${GREEN}  - 新创建: $created_count 个目录${NC}"
echo -e "${GRAY}  - 已存在: $existing_count 个目录${NC}"

# 设置目录权限
echo -e "${YELLOW}"
echo "🔧 设置目录权限..."
echo -e "${NC}"

for dir in "${directories[@]}"; do
    chmod 755 "$dir"
    echo -e "${GREEN}  ✅ 设置 $dir 权限: 755${NC}"
done

# 创建 .gitkeep 文件（保持目录结构在 Git 中）
echo -e "${YELLOW}"
echo "📝 创建 .gitkeep 文件..."
echo -e "${NC}"

gitkeep_dirs=("logs" "data" "runtime")
for dir in "${gitkeep_dirs[@]}"; do
    gitkeep_file="$dir/.gitkeep"
    if [ ! -f "$gitkeep_file" ]; then
        touch "$gitkeep_file"
        echo -e "${GREEN}  ✅ 创建: $gitkeep_file${NC}"
    fi
done

echo -e "${GREEN}"
echo "✅ 目录初始化完成！"
echo -e "${NC}"

echo -e "${CYAN}📋 下一步操作：${NC}"
echo "  1. 配置环境变量：复制 .env.example 为 .env 并编辑"
echo "  2. 下载 Nginx 配置：运行 ./deploy.sh 或手动下载"
echo "  3. 启动服务：docker-compose -f docker-compose.compiled.yml up -d"
echo ""

