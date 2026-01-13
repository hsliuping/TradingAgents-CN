# Docker 编译版测试指南

本文档说明如何在 Ubuntu 22.04 服务器上测试新的 Docker 编译版配置。

## 📋 测试环境要求

- **操作系统**: Ubuntu 22.04 LTS
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **磁盘空间**: 至少 10 GB
- **内存**: 至少 4 GB

## 🧪 测试步骤

### 步骤 1: 准备环境

```bash
# 1. 克隆代码（如果还没有）
git clone https://github.com/your-repo/TradingAgentsCN.git
cd TradingAgentsCN

# 2. 检查 Docker 版本
docker --version
docker-compose --version

# 3. 确保 Docker 服务运行
sudo systemctl status docker
```

### 步骤 2: 配置环境变量

```bash
# 1. 复制环境变量文件
cp docker/.env.docker .env

# 2. 编辑配置（至少配置一个 LLM API 密钥）
nano .env

# 最小配置示例:
# DASHSCOPE_API_KEY=sk-xxx
# DASHSCOPE_ENABLED=true
```

### 步骤 3: 编译代码

```bash
# 1. 进入 docker 目录
cd docker

# 2. 给脚本添加执行权限
chmod +x scripts/*.sh

# 3. 运行编译脚本
./scripts/compile-code.sh

# 4. 检查编译结果
ls -la build/compiled/
ls -la build/compiled/app/
ls -la build/compiled/core/

# 应该看到很多 .pyc 文件
find build/compiled -name "*.pyc" | wc -l
```

### 步骤 4: 构建 Docker 镜像

```bash
# 1. 构建后端镜像（编译版）
docker-compose -f docker-compose.compiled.yml build backend

# 2. 构建前端镜像
docker-compose -f docker-compose.compiled.yml build frontend

# 3. 检查镜像
docker images | grep tradingagents
```

### 步骤 5: 启动服务

```bash
# 1. 启动所有服务
docker-compose -f docker-compose.compiled.yml up -d

# 2. 查看服务状态
docker-compose -f docker-compose.compiled.yml ps

# 3. 查看日志
docker-compose -f docker-compose.compiled.yml logs -f
```

### 步骤 6: 验证服务

```bash
# 1. 等待服务启动（约 30-60 秒）
sleep 60

# 2. 检查后端健康状态
curl http://localhost/api/health

# 应该返回: {"status":"ok"}

# 3. 检查前端
curl -I http://localhost/

# 应该返回: HTTP/1.1 200 OK

# 4. 在浏览器中访问
# http://your-server-ip/
```

### 步骤 7: 功能测试

1. **登录测试**:
   - 访问 `http://your-server-ip/`
   - 使用默认账号登录（如果已初始化）

2. **API 测试**:
   ```bash
   # 测试 API 端点
   curl http://localhost/api/health
   curl http://localhost/api/system/info
   ```

3. **数据库测试**:
   ```bash
   # 进入 MongoDB 容器
   docker exec -it tradingagents-mongodb mongo -u admin -p tradingagents123 --authenticationDatabase admin
   
   # 查看数据库
   show dbs
   use tradingagents
   show collections
   ```

4. **Redis 测试**:
   ```bash
   # 进入 Redis 容器
   docker exec -it tradingagents-redis redis-cli -a tradingagents123
   
   # 测试连接
   PING
   # 应该返回: PONG
   ```

## ✅ 验证清单

- [ ] 编译脚本成功运行
- [ ] 生成了 `.pyc` 文件
- [ ] Docker 镜像构建成功
- [ ] 所有服务启动成功
- [ ] 后端健康检查通过
- [ ] 前端页面可访问
- [ ] MongoDB 连接正常
- [ ] Redis 连接正常
- [ ] 可以正常登录
- [ ] API 调用正常

## 🐛 常见问题

### 问题 1: 编译失败

**症状**: `compile-code.sh` 报错

**解决方案**:
```bash
# 检查 Python 版本
python3 --version  # 应该是 3.10+

# 检查源代码是否完整
ls -la ../app
ls -la ../core
```

### 问题 2: Docker 构建失败

**症状**: `docker-compose build` 报错

**解决方案**:
```bash
# 清理 Docker 缓存
docker builder prune -a

# 重新构建
docker-compose -f docker-compose.compiled.yml build --no-cache
```

### 问题 3: 服务启动失败

**症状**: 容器不断重启

**解决方案**:
```bash
# 查看日志
docker-compose -f docker-compose.compiled.yml logs backend

# 检查环境变量
docker-compose -f docker-compose.compiled.yml config

# 检查端口占用
sudo netstat -tulpn | grep -E '80|8000|27017|6379'
```

### 问题 4: 无法访问前端

**症状**: `curl http://localhost/` 失败

**解决方案**:
```bash
# 检查 Nginx 状态
docker-compose -f docker-compose.compiled.yml logs nginx

# 检查 Nginx 配置
docker exec tradingagents-nginx cat /etc/nginx/nginx.conf

# 检查前端容器
docker-compose -f docker-compose.compiled.yml logs frontend
```

## 🧹 清理测试环境

```bash
# 1. 停止所有服务
docker-compose -f docker-compose.compiled.yml down

# 2. 删除数据卷（可选）
docker-compose -f docker-compose.compiled.yml down -v

# 3. 删除镜像（可选）
docker rmi hsliup/tradingagents-backend:latest
docker rmi hsliup/tradingagents-frontend:latest

# 4. 清理编译目录
rm -rf build/compiled
```

## 📝 测试报告模板

测试完成后，请填写以下信息：

```
测试日期: ____________________
测试人员: ____________________
服务器环境: Ubuntu 22.04 / 其他 ____________________
Docker 版本: ____________________
Docker Compose 版本: ____________________

测试结果:
- [ ] 编译成功
- [ ] 构建成功
- [ ] 启动成功
- [ ] 功能正常

遇到的问题:
____________________
____________________

建议改进:
____________________
____________________
```

---

**最后更新**: 2026-01-13  
**版本**: v1.0.0

