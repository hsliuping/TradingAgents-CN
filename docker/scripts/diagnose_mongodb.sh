#!/bin/bash
# MongoDB 诊断脚本

echo "=========================================="
echo "MongoDB 诊断工具"
echo "=========================================="
echo ""

# 1. 检查 MongoDB 容器状态
echo "[1/5] 检查 MongoDB 容器状态..."
MONGODB_CONTAINER=$(docker ps -a --filter "name=mongodb" --format "{{.Names}}" | head -n 1)

if [ -z "$MONGODB_CONTAINER" ]; then
    echo "❌ 未找到 MongoDB 容器"
    echo "   请检查 docker-compose.yml 中的服务配置"
else
    echo "✅ 找到容器: $MONGODB_CONTAINER"
    
    # 检查容器状态
    CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' "$MONGODB_CONTAINER" 2>/dev/null)
    echo "   状态: $CONTAINER_STATUS"
    
    if [ "$CONTAINER_STATUS" != "running" ]; then
        echo "⚠️  容器未运行，尝试启动..."
        docker start "$MONGODB_CONTAINER"
        sleep 5
    fi
fi

echo ""

# 2. 检查网络连接
echo "[2/5] 检查网络连接..."
if docker network inspect tradingagents-network >/dev/null 2>&1; then
    echo "✅ 网络 tradingagents-network 存在"
    
    # 检查 MongoDB 是否在网络上
    if docker network inspect tradingagents-network | grep -q "$MONGODB_CONTAINER"; then
        echo "✅ MongoDB 容器在网络中"
    else
        echo "⚠️  MongoDB 容器不在网络中，尝试连接..."
        docker network connect tradingagents-network "$MONGODB_CONTAINER" 2>/dev/null || true
    fi
else
    echo "❌ 网络 tradingagents-network 不存在"
    echo "   请运行: docker network create tradingagents-network"
fi

echo ""

# 3. 测试 MongoDB 连接
echo "[3/5] 测试 MongoDB 连接..."
if docker exec "$MONGODB_CONTAINER" mongosh --eval "db.runCommand('ping')" >/dev/null 2>&1; then
    echo "✅ MongoDB 内部连接正常"
else
    echo "❌ MongoDB 内部连接失败"
    echo "   查看容器日志: docker logs $MONGODB_CONTAINER"
fi

echo ""

# 4. 从后端容器测试连接
echo "[4/5] 从后端容器测试 MongoDB 连接..."
BACKEND_CONTAINER=$(docker ps --filter "name=backend" --format "{{.Names}}" | head -n 1)

if [ -n "$BACKEND_CONTAINER" ]; then
    echo "   使用后端容器: $BACKEND_CONTAINER"
    if docker exec "$BACKEND_CONTAINER" python -c "
from pymongo import MongoClient
try:
    client = MongoClient('mongodb://admin:tradingagents123@mongodb:27017/tradingagents?authSource=admin', serverSelectionTimeoutMS=5000)
    client.server_info()
    print('✅ 连接成功')
except Exception as e:
    print(f'❌ 连接失败: {e}')
" 2>&1; then
        echo "✅ 后端容器可以连接到 MongoDB"
    else
        echo "❌ 后端容器无法连接到 MongoDB"
    fi
else
    echo "⚠️  后端容器未运行"
fi

echo ""

# 5. 检查数据卷
echo "[5/5] 检查 MongoDB 数据卷..."
VOLUMES=$(docker volume ls --filter "name=mongodb" --format "{{.Name}}")
if [ -n "$VOLUMES" ]; then
    echo "✅ 找到数据卷:"
    echo "$VOLUMES" | while read vol; do
        echo "   - $vol"
        VOL_SIZE=$(docker volume inspect "$vol" --format '{{.Mountpoint}}' 2>/dev/null | xargs du -sh 2>/dev/null | cut -f1)
        echo "     大小: ${VOL_SIZE:-未知}"
    done
else
    echo "⚠️  未找到 MongoDB 数据卷"
fi

echo ""
echo "=========================================="
echo "诊断完成"
echo "=========================================="
echo ""
echo "如果 MongoDB 连接失败，可以尝试："
echo "1. 重启 MongoDB 容器: docker restart $MONGODB_CONTAINER"
echo "2. 删除并重建数据卷（会丢失数据）:"
echo "   docker-compose down -v"
echo "   docker volume rm tradingagents_mongodb_data"
echo "   docker-compose up -d mongodb"
echo "3. 查看 MongoDB 日志: docker logs $MONGODB_CONTAINER"
