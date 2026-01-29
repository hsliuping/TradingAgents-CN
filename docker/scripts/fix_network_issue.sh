#!/bin/bash
# 修复 Docker 网络问题的脚本
# 用于解决容器不在同一网络导致的连接问题

echo "=========================================="
echo "修复 Docker 网络配置"
echo "=========================================="
echo ""

# 获取当前目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$DOCKER_DIR"

echo "1. 停止并删除所有相关容器..."
docker-compose -f docker-compose.compiled.yml down

echo ""
echo "2. 检查并清理孤立的网络..."
# 查找所有 tradingagents 相关的网络
NETWORKS=$(docker network ls --filter "name=tradingagents" --format "{{.Name}}")
if [ -n "$NETWORKS" ]; then
    echo "找到以下网络:"
    echo "$NETWORKS"
    echo ""
    read -p "是否删除这些网络? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for net in $NETWORKS; do
            echo "删除网络: $net"
            docker network rm "$net" 2>/dev/null || echo "  网络 $net 可能正在使用中，跳过"
        done
    fi
fi

echo ""
echo "3. 重新创建并启动所有服务..."
docker-compose -f docker-compose.compiled.yml up -d

echo ""
echo "4. 等待服务启动..."
sleep 5

echo ""
echo "5. 检查容器状态..."
docker-compose -f docker-compose.compiled.yml ps

echo ""
echo "6. 检查网络配置..."
docker network inspect tradingagents-network 2>/dev/null | grep -A 10 "Containers" || echo "网络检查失败"

echo ""
echo "=========================================="
echo "完成！"
echo "=========================================="
echo ""
echo "如果仍有问题，请检查："
echo "1. docker logs tradingagents-mongodb-propro"
echo "2. docker logs tradingagents-backend-pro"
echo "3. docker network inspect tradingagents-network"
