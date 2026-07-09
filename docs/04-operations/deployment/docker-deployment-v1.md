# TradingAgents-CN v1.0.0-preview Docker部署指南

> 🐳 使用Docker快速部署TradingAgents-CN（前后端分离架构）

## 📋 架构说明

TradingAgents-CN v1.0.0-preview采用**前后端分离架构**：

- **后端**: FastAPI + Python 3.10 (端口: 8000)
- **前端**: Vue 3 + Vite + Nginx (端口: 5173)
- **数据库**: MongoDB 4.4 (端口: 27017)
- **缓存**: Redis 7 (端口: 6379)

### Docker文件说明

| 文件 | 用途 |
|------|------|
| **Dockerfile.backend** | 后端服务镜像（FastAPI） |
| **Dockerfile.frontend** | 前端服务镜像（Vue 3 + Nginx） |
| **docker-compose.v1.0.0.yml** | Docker Compose配置（前后端分离） |
| **docker/nginx.conf** | Nginx配置（前端静态文件服务） |

> 📝 **注意**: `Dockerfile.legacy`是旧版Streamlit应用，不适用于v1.0.0版本。

---

## 📋 前置要求

### 必需

- **Docker** 20.10+
- **Docker Compose** 2.0+
- **至少4GB内存** 和 **20GB磁盘空间**
- **至少一个LLM API密钥**

### 检查Docker版本

```bash
docker --version
# Docker version 20.10.0 或更高

docker-compose --version
# Docker Compose version 2.0.0 或更高
```

---

## 🚀 快速部署

### 方式一：使用初始化脚本（推荐）

#### Linux/macOS

```bash
# 1. 克隆仓库
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 配置环境变量
cp .env.example .env
nano .env  # 编辑配置文件

# 3. 运行初始化脚本
chmod +x scripts/docker-init.sh
./scripts/docker-init.sh
```

#### Windows (PowerShell)

```powershell
# 1. 克隆仓库
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 配置环境变量
Copy-Item .env.example .env
notepad .env  # 编辑配置文件

# 3. 运行初始化脚本
.\scripts\docker-init.ps1
```

### 方式二：手动部署

```bash
# 1. 克隆仓库
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置API密钥

# 3. 创建必需的目录
mkdir -p logs data/cache data/exports data/reports config

# 4. 启动服务
docker-compose -f docker-compose.v1.0.0.yml up -d

# 5. 查看日志
docker-compose -f docker-compose.v1.0.0.yml logs -f
```

---

## 🔧 配置说明

### 最小配置

编辑 `.env` 文件，配置以下必需项：

```bash
# 1. LLM API密钥（至少配置一个）
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
DEEPSEEK_ENABLED=true

# 2. JWT密钥（生产环境必须修改）
JWT_SECRET=your-super-secret-jwt-key-change-in-production

# 3. 数据源（可选，推荐）
TUSHARE_TOKEN=your-tushare-token-here
TUSHARE_ENABLED=true
```

### 完整配置

详见 [.env.example](.env.example) 文件

---

## 📦 服务说明

### 核心服务

| 服务 | 端口 | 说明 |
|-----|------|------|
| **frontend** | 5173 | Vue 3前端界面 |
| **backend** | 8000 | FastAPI后端API |
| **mongodb** | 27017 | MongoDB数据库 |
| **redis** | 6379 | Redis缓存 |

### 管理服务（可选）

| 服务 | 端口 | 说明 |
|-----|------|------|
| **mongo-express** | 8082 | MongoDB管理界面 |
| **redis-commander** | 8081 | Redis管理界面 |

启动管理服务：

```bash
docker-compose -f docker-compose.v1.0.0.yml --profile management up -d
```

---

## 🎯 访问应用

### 主要入口

- **前端界面**: http://localhost:5173
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc

### 管理界面（可选）

- **MongoDB管理**: http://localhost:8082
  - 用户名: `admin`
  - 密码: `tradingagents123`

- **Redis管理**: http://localhost:8081

### 默认账号

- **用户名**: `admin`
- **密码**: `admin123`

⚠️ **重要**: 请在首次登录后立即修改密码！

---

## 🔍 常用命令

### 服务管理

```bash
# 启动所有服务
docker-compose -f docker-compose.v1.0.0.yml up -d

# 停止所有服务
docker-compose -f docker-compose.v1.0.0.yml down

# 重启所有服务
docker-compose -f docker-compose.v1.0.0.yml restart

# 重启单个服务
docker-compose -f docker-compose.v1.0.0.yml restart backend

# 查看服务状态
docker-compose -f docker-compose.v1.0.0.yml ps

# 查看服务日志
docker-compose -f docker-compose.v1.0.0.yml logs -f

# 查看单个服务日志
docker-compose -f docker-compose.v1.0.0.yml logs -f backend
```

### 数据管理

```bash
# 备份MongoDB数据
docker exec tradingagents-mongodb mongodump --out /data/backup

# 恢复MongoDB数据
docker exec tradingagents-mongodb mongorestore /data/backup

# 清理Redis缓存
docker exec tradingagents-redis redis-cli -a tradingagents123 FLUSHALL

# 查看MongoDB数据
docker exec -it tradingagents-mongodb mongo -u admin -p tradingagents123
```

### 容器管理

```bash
# 进入后端容器
docker exec -it tradingagents-backend bash

# 进入前端容器
docker exec -it tradingagents-frontend sh

# 查看容器资源使用
docker stats

# 清理未使用的容器和镜像
docker system prune -a
```

---

## 🐛 故障排除

### 问题1：端口被占用

**错误**: `Bind for 0.0.0.0:5173 failed: port is already allocated`

**解决方案**:

```bash
# 查找占用端口的进程
# Linux/macOS
lsof -i :5173

# Windows
netstat -ano | findstr :5173

# 修改端口（编辑docker-compose.v1.0.0.yml）
ports:
  - "5174:80"  # 改为其他端口
```

### 问题2：MongoDB连接失败

**错误**: `MongoServerError: Authentication failed`

**解决方案**:

```bash
# 1. 停止所有服务
docker-compose -f docker-compose.v1.0.0.yml down -v

# 2. 删除数据卷
docker volume rm tradingagents_mongodb_data_v1

# 3. 重新启动
docker-compose -f docker-compose.v1.0.0.yml up -d
```

### 问题3：前端无法连接后端

**错误**: 前端显示"网络错误"

**解决方案**:

```bash
# 1. 检查后端是否运行
curl http://localhost:8000/health

# 2. 检查CORS配置
# 编辑 .env 文件
CORS_ORIGINS=http://localhost:5173,http://localhost:8080

# 3. 重启后端
docker-compose -f docker-compose.v1.0.0.yml restart backend
```

### 问题4：内存不足

**错误**: 容器频繁重启或OOM

**解决方案**:

```bash
# 1. 检查Docker资源限制
# Docker Desktop -> Settings -> Resources
# 建议: 4GB+ 内存

# 2. 减少并发任务数
# 编辑 .env 文件
MAX_CONCURRENT_ANALYSIS_TASKS=1

# 3. 清理缓存
docker exec tradingagents-redis redis-cli -a tradingagents123 FLUSHALL
```

### 问题5：构建失败

**错误**: `ERROR [internal] load metadata for docker.io/library/python:3.10`

**解决方案**:

```bash
# 1. 检查网络连接
ping docker.io

# 2. 配置Docker镜像加速
# 编辑 /etc/docker/daemon.json (Linux)
# 或 Docker Desktop -> Settings -> Docker Engine (Windows/macOS)
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}

# 3. 重启Docker
sudo systemctl restart docker  # Linux
# 或重启Docker Desktop

# 4. 重新构建
docker-compose -f docker-compose.v1.0.0.yml build --no-cache
```

---

## 🔐 安全建议

### 生产环境配置

1. **修改默认密码**

```bash
# MongoDB密码
MONGO_INITDB_ROOT_PASSWORD=your-strong-password-here

# Redis密码
REDIS_PASSWORD=your-strong-password-here

# JWT密钥
JWT_SECRET=your-super-secret-jwt-key-change-in-production
```

2. **限制端口访问**

```yaml
# 只在本地访问
ports:
  - "127.0.0.1:27017:27017"  # MongoDB
  - "127.0.0.1:6379:6379"    # Redis
```

3. **启用HTTPS**

使用Nginx反向代理并配置SSL证书

4. **定期备份**

```bash
# 创建备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker exec tradingagents-mongodb mongodump --out /data/backup_$DATE
```

---

## 📊 性能优化

### 1. 调整资源限制

编辑 `docker-compose.v1.0.0.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 2. 优化MongoDB

```bash
# 进入MongoDB容器
docker exec -it tradingagents-mongodb mongo -u admin -p tradingagents123

# 创建索引
use tradingagents
db.analysis_reports.createIndex({ "symbol": 1, "created_at": -1 })
```

### 3. 优化Redis

```bash
# 配置Redis持久化策略
# 编辑docker-compose.v1.0.0.yml
command: redis-server --appendonly yes --save 60 1000
```

---

## 📚 更多资源

- [完整文档](docs/v1.0.0-preview/)
- [API文档](http://localhost:8000/docs)
- [故障排除](docs/v1.0.0-preview/07-deployment/05-troubleshooting.md)
- [性能优化](docs/v1.0.0-preview/07-deployment/03-performance-tuning.md)

---

## 🤝 获取帮助

- **GitHub Issues**: https://github.com/hsliuping/TradingAgents-CN/issues
- **QQ群**: 782124367
- **邮箱**: hsliup@163.com

---

**版本**: v1.0.0-preview  
**更新日期**: 2025-10-15  
**维护者**: TradingAgents-CN Team

