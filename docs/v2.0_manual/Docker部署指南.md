# Docker 部署指南

> TradingAgentsCN v2.0 Docker 快速部署手册

## 📋 目录

- [前置要求](#前置要求)
- [快速开始](#快速开始)
- [详细步骤](#详细步骤)
- [配置说明](#配置说明)
- [常用操作](#常用操作)
- [故障排除](#故障排除)

## 前置要求

### 系统要求

- **操作系统**: Windows 10/11, Linux (Ubuntu 20.04+), macOS 10.15+
- **Docker**: Docker Desktop 4.0+ 或 Docker Engine 20.10+
- **Docker Compose**: 2.0+（通常随 Docker Desktop 一起安装）
- **内存**: 至少 8GB RAM（推荐 16GB）
- **磁盘空间**: 至少 20GB 可用空间
- **网络**: 稳定的互联网连接

### 安装 Docker

#### Windows 用户

1. 下载并安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
2. 安装完成后重启电脑
3. 启动 Docker Desktop
4. 等待 Docker 启动完成（系统托盘图标变为绿色）

#### Linux 用户

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
docker --version
docker-compose --version
```

#### macOS 用户

1. 下载并安装 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
2. 启动 Docker Desktop
3. 等待 Docker 启动完成

## 快速开始

### 一键部署（推荐）

```bash
# 1. 克隆项目（或下载 ZIP 包）
git clone https://github.com/your-repo/TradingAgentsCN.git
cd TradingAgentsCN

# 2. 配置环境变量
cp docker/.env.example .env
# 编辑 .env 文件，配置 API 密钥（见下方配置说明）

# 3. 启动所有服务
cd docker
docker-compose -f docker-compose.compiled.yml up -d

# 4. 等待服务启动（约 1-2 分钟）
docker-compose -f docker-compose.compiled.yml ps

# 5. 访问应用
# 浏览器打开: http://localhost:8082
```

## 详细步骤

### 步骤 1: 准备项目文件

```bash
# 方式 A: 从 Git 克隆
git clone https://github.com/your-repo/TradingAgentsCN.git
cd TradingAgentsCN

# 方式 B: 下载 ZIP 包
# 1. 从 GitHub 下载 ZIP 包
# 2. 解压到本地目录
# 3. 进入解压后的目录
```

### 步骤 2: 配置环境变量

```bash
# 复制环境变量模板
# Windows (PowerShell)
Copy-Item docker\.env.example .env

# Linux/macOS
cp docker/.env.example .env

# 编辑环境变量文件
# Windows: 使用记事本或 VS Code
notepad .env

# Linux/macOS: 使用 nano 或 vim
nano .env
```

**必须配置的变量**（至少配置一个 LLM 提供商）：

```env
# LLM API 密钥（至少配置一个）
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# 数据源 API 密钥（可选）
TUSHARE_TOKEN=your_tushare_token_here
FINNHUB_API_KEY=your_finnhub_api_key_here

# 安全配置（生产环境必须修改）
JWT_SECRET=your_random_jwt_secret_here
CSRF_SECRET=your_random_csrf_secret_here
```

**可选配置**（使用默认值即可）：

```env
# MongoDB 配置（默认值，通常不需要修改）
MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_USERNAME=admin
MONGODB_PASSWORD=tradingagents123
MONGODB_DATABASE=tradingagents

# Redis 配置（默认值，通常不需要修改）
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=tradingagents123
```

### 步骤 3: 启动服务

```bash
# 进入 docker 目录
cd docker

# 启动所有服务（后台运行）
docker-compose -f docker-compose.compiled.yml up -d

# 查看服务状态
docker-compose -f docker-compose.compiled.yml ps
```

**服务说明**：

- **mongodb**: MongoDB 数据库（端口：27017）
- **redis**: Redis 缓存（端口：6379）
- **backend**: 后端 API 服务（内部端口：8000）
- **frontend**: 前端 Web 服务（内部端口：80）
- **nginx**: Nginx 反向代理（对外端口：8082）

### 步骤 4: 验证部署

1. **检查容器状态**：

```bash
docker-compose -f docker-compose.compiled.yml ps
```

所有服务的状态应该显示为 `Up`。

2. **查看日志**：

```bash
# 查看所有服务日志
docker-compose -f docker-compose.compiled.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.compiled.yml logs -f backend
docker-compose -f docker-compose.compiled.yml logs -f frontend
```

3. **访问应用**：

打开浏览器访问：`http://localhost:8082`

如果看到登录页面，说明部署成功！

### 步骤 5: 首次登录

1. 打开浏览器访问：`http://localhost:8082`
2. 首次使用需要注册账号
3. 注册完成后登录系统
4. 进入 **设置** → **配置管理** 配置 LLM 提供商和数据源

## 配置说明

### 环境变量详解

#### LLM 提供商配置

```env
# 阿里云百炼（DashScope）
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxx
DASHSCOPE_ENABLED=true

# DeepSeek
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
DEEPSEEK_ENABLED=true

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
OPENAI_ENABLED=true

# Google AI
GOOGLE_API_KEY=your_google_api_key
GOOGLE_ENABLED=false

# 百度千帆
BAIDU_API_KEY=your_baidu_api_key
BAIDU_SECRET_KEY=your_baidu_secret_key
BAIDU_ENABLED=false
```

#### 数据源配置

```env
# Tushare（A股数据）
TUSHARE_TOKEN=your_tushare_token
TUSHARE_ENABLED=true

# AKShare（免费数据源）
AKSHARE_ENABLED=true

# BaoStock（免费数据源）
BAOSTOCK_ENABLED=true

# Finnhub（美股数据）
FINNHUB_API_KEY=your_finnhub_api_key
FINNHUB_ENABLED=false
```

#### 安全配置（生产环境必须修改）

```env
# JWT 密钥（用于用户认证）
JWT_SECRET=your_random_secret_key_at_least_32_characters

# CSRF 密钥（用于防止跨站请求伪造）
CSRF_SECRET=your_random_secret_key_at_least_32_characters

# Token 过期时间
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=30
```

**生成随机密钥的方法**：

```bash
# Linux/macOS
openssl rand -hex 32

# Windows PowerShell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
```

### 端口配置

默认端口配置：

- **8082**: Nginx 反向代理（对外访问端口）
- **27017**: MongoDB（数据库）
- **6379**: Redis（缓存）

如需修改端口，编辑 `docker-compose.compiled.yml`：

```yaml
nginx:
  ports:
    - "8082:8082"  # 修改为 "80:8082" 使用 80 端口
```

### 数据持久化

数据存储在 Docker 卷中，即使删除容器也不会丢失：

```bash
# 查看数据卷
docker volume ls | grep tradingagents

# 备份数据卷
docker run --rm -v tradingagents_mongodb_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/mongodb_backup.tar.gz /data
```

## 常用操作

### 启动服务

```bash
cd docker
docker-compose -f docker-compose.compiled.yml up -d
```

### 停止服务

```bash
cd docker
docker-compose -f docker-compose.compiled.yml down
```

### 重启服务

```bash
cd docker
docker-compose -f docker-compose.compiled.yml restart

# 重启特定服务
docker-compose -f docker-compose.compiled.yml restart backend
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose -f docker-compose.compiled.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.compiled.yml logs -f backend
docker-compose -f docker-compose.compiled.yml logs -f frontend
docker-compose -f docker-compose.compiled.yml logs -f mongodb
```

### 更新镜像

```bash
# 拉取最新镜像
docker pull hsliup/tradingagents-pro-backend:latest
docker pull hsliup/tradingagents-pro-frontend:latest

# 重启服务（使用新镜像）
cd docker
docker-compose -f docker-compose.compiled.yml up -d --force-recreate
```

### 进入容器（调试用）

```bash
# 进入后端容器
docker-compose -f docker-compose.compiled.yml exec backend bash

# 进入前端容器
docker-compose -f docker-compose.compiled.yml exec frontend sh

# 进入 MongoDB 容器
docker-compose -f docker-compose.compiled.yml exec mongodb bash
```

### 备份数据

```bash
# 备份 MongoDB 数据
docker-compose -f docker-compose.compiled.yml exec mongodb \
  mongodump --out /data/backup --username admin --password tradingagents123 --authenticationDatabase admin

# 备份整个数据卷
docker run --rm \
  -v tradingagents_mongodb_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/mongodb_backup_$(date +%Y%m%d).tar.gz /data
```

### 恢复数据

```bash
# 恢复 MongoDB 数据
docker-compose -f docker-compose.compiled.yml exec mongodb \
  mongorestore /data/backup --username admin --password tradingagents123 --authenticationDatabase admin
```

### 清理数据（谨慎使用！）

```bash
# 停止并删除所有容器、网络、数据卷
docker-compose -f docker-compose.compiled.yml down -v

# 清理未使用的镜像
docker image prune -a
```

## 故障排除

### 问题 1: 容器无法启动

**检查步骤**：

1. 检查 Docker 是否正常运行：
```bash
docker ps
```

2. 查看错误日志：
```bash
docker-compose -f docker-compose.compiled.yml logs
```

3. 检查端口是否被占用：
```bash
# Windows
netstat -ano | findstr :8082

# Linux/macOS
lsof -i :8082
```

**解决方案**：

- 如果端口被占用，修改 `docker-compose.compiled.yml` 中的端口映射
- 检查 `.env` 文件配置是否正确
- 确保有足够的磁盘空间和内存

### 问题 2: 无法访问前端页面

**检查步骤**：

1. 检查容器状态：
```bash
docker-compose -f docker-compose.compiled.yml ps
```

2. 检查 Nginx 日志：
```bash
docker-compose -f docker-compose.compiled.yml logs nginx
```

3. 检查前端容器：
```bash
docker-compose -f docker-compose.compiled.yml logs frontend
```

**解决方案**：

- 等待所有容器完全启动（约 1-2 分钟）
- 检查防火墙设置
- 尝试访问 `http://localhost:8082/health` 检查健康状态

### 问题 3: 后端 API 调用失败

**检查步骤**：

1. 检查后端日志：
```bash
docker-compose -f docker-compose.compiled.yml logs backend
```

2. 检查 MongoDB 连接：
```bash
docker-compose -f docker-compose.compiled.yml exec backend \
  python -c "from app.core.database import get_mongo_db_sync; print(get_mongo_db_sync())"
```

3. 检查 API 健康状态：
```bash
curl http://localhost:8082/api/health
```

**解决方案**：

- 检查 `.env` 文件中的 MongoDB 配置
- 确保 MongoDB 容器已启动并健康
- 检查 API 密钥配置是否正确

### 问题 4: 数据库连接失败

**检查步骤**：

1. 检查 MongoDB 容器状态：
```bash
docker-compose -f docker-compose.compiled.yml ps mongodb
```

2. 检查 MongoDB 日志：
```bash
docker-compose -f docker-compose.compiled.yml logs mongodb
```

3. 测试 MongoDB 连接：
```bash
docker-compose -f docker-compose.compiled.yml exec mongodb \
  mongo --username admin --password tradingagents123 --authenticationDatabase admin
```

**解决方案**：

- 重启 MongoDB 容器：`docker-compose -f docker-compose.compiled.yml restart mongodb`
- 检查 `.env` 文件中的 MongoDB 用户名和密码
- 检查数据卷是否正确挂载

### 问题 5: 镜像拉取失败

**检查步骤**：

1. 检查网络连接：
```bash
ping hub.docker.com
```

2. 检查 Docker Hub 登录状态：
```bash
docker login
```

**解决方案**：

- 检查网络连接和代理设置
- 如果使用国内网络，考虑配置 Docker 镜像加速器
- 手动拉取镜像：`docker pull hsliup/tradingagents-pro-backend:latest`

### 问题 6: 内存不足

**症状**：容器频繁重启，日志显示 OOM（Out of Memory）

**解决方案**：

1. 增加 Docker 内存限制（Docker Desktop）：
   - 打开 Docker Desktop 设置
   - 进入 Resources → Advanced
   - 增加 Memory 限制（至少 8GB）

2. 减少并发任务数量（在系统设置中配置）

3. 关闭不必要的容器和服务

## 生产环境部署建议

### 1. 使用 HTTPS

配置反向代理（Nginx）并启用 SSL 证书：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8082;
    }
}
```

### 2. 修改默认密码

生产环境必须修改以下默认密码：

- MongoDB root 密码
- Redis 密码
- JWT 和 CSRF 密钥

### 3. 配置防火墙

只开放必要的端口：

```bash
# Linux (UFW)
sudo ufw allow 8082/tcp
sudo ufw enable

# Windows Firewall
# 在 Windows 防火墙中只开放 8082 端口
```

### 4. 定期备份

设置定时任务自动备份数据：

```bash
# Linux cron 示例
0 2 * * * /path/to/backup-script.sh
```

### 5. 监控和日志

- 配置日志轮转
- 使用 Docker 监控工具（如 Portainer）
- 设置告警通知

## 相关资源

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [项目 GitHub 仓库](https://github.com/your-repo/TradingAgentsCN)
- [Docker Hub 镜像](https://hub.docker.com/r/hsliup/tradingagents-pro-backend)

## 获取帮助

如遇到问题，可以通过以下方式获取帮助：

- GitHub Issues
- 社区论坛
- 技术支持邮箱

---

**最后更新**: 2026-01-16  
**版本**: v2.0
