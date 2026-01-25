# TradingAgents-CN Pro - Docker 一键部署指南

## 📋 概述

本目录提供了 TradingAgents-CN Pro 的 Docker 一键部署脚本，支持 Linux/macOS 和 Windows 平台。

---

## 🚀 快速开始

### Linux / macOS

```bash
# 1. 进入部署目录
cd tradingagents-demo-v2

# 2. 赋予执行权限
chmod +x deploy.sh

# 3. 运行部署脚本
./deploy.sh
```

### Windows (PowerShell)

```powershell
# 1. 进入部署目录
cd tradingagents-demo-v2

# 2. 运行部署脚本
.\deploy.ps1
```

---

## 📦 脚本功能

一键部署脚本会自动完成以下操作：

1. ✅ **检查依赖**
   - 检查 Docker 是否已安装
   - 检查 docker-compose 是否可用
   - (Linux) 检查 wget 是否已安装

2. ✅ **下载 Docker Compose 配置**
   - 自动下载 `docker-compose.compiled.yml` 文件
   - 如果文件已存在，会询问是否覆盖

3. ✅ **创建目录**
   - 创建 `nginx/` 目录
   - 创建 `logs/`、`data/`、`runtime/` 目录

4. ✅ **下载 Nginx 配置**
   - 自动下载 Nginx 配置文件到 `nginx/nginx-proxy.conf`
   - 如果文件已存在，会询问是否覆盖

5. ✅ **配置环境变量**
   - 从 `.env.example` 创建 `.env` 文件
   - 提示用户编辑配置（可选）

6. ✅ **启动服务**
   - 拉取最新 Docker 镜像
   - 启动所有服务（MongoDB、Redis、Backend、Frontend、Nginx）

7. ✅ **显示状态**
   - 显示服务运行状态
   - 显示访问地址和默认账号密码

---

## 🔧 前置要求

### 所有平台

- **Docker**: 20.10+
- **Docker Compose**: 1.29+

### Linux / macOS

- **wget**: 用于下载配置文件
  ```bash
  # Ubuntu/Debian
  sudo apt-get install wget
  
  # macOS
  brew install wget
  ```

### Windows

- **Docker Desktop**: 包含 Docker 和 docker-compose
  - 下载地址: https://www.docker.com/products/docker-desktop

---

## 📁 部署目录结构

部署完成后，目录结构如下：

```
tradingagents-demo-v2/
├── docker-compose.compiled.yml  # Docker Compose 配置文件
├── .env                          # 环境变量文件
├── deploy.sh                     # Linux/macOS 部署脚本
├── deploy.ps1                    # Windows 部署脚本
├── nginx/
│   └── nginx-proxy.conf          # Nginx 配置文件（自动下载）
├── logs/                         # 日志目录（自动创建）
├── data/                         # 数据目录（自动创建）
└── runtime/                      # 运行时目录（自动创建）
```

---

## 🌐 访问信息

部署成功后，可以通过以下地址访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端界面** | http://localhost:8082 | Web 用户界面 |
| **后端 API** | http://localhost:8082/api | RESTful API |
| **API 文档** | http://localhost:8082/api/docs | Swagger 文档 |

**默认账号**:
- 用户名: `admin`
- 密码: `admin123`

---

## 🛠️ 常用命令

### 查看服务状态

```bash
docker-compose -f docker-compose.compiled.yml ps
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose -f docker-compose.compiled.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.compiled.yml logs -f backend
docker-compose -f docker-compose.compiled.yml logs -f frontend
```

### 停止服务

```bash
docker-compose -f docker-compose.compiled.yml down
```

### 重启服务

```bash
docker-compose -f docker-compose.compiled.yml restart
```

### 重新部署

```bash
# 停止并删除容器
docker-compose -f docker-compose.compiled.yml down

# 重新运行部署脚本
./deploy.sh  # Linux/macOS
.\deploy.ps1  # Windows
```

---

## ⚙️ 环境变量配置

`.env` 文件中的重要配置项：

```bash
# MongoDB 配置
MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_USERNAME=admin
MONGODB_PASSWORD=your_password_here

# Redis 配置
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password_here

# 后端配置
BACKEND_PORT=8000
SECRET_KEY=your_secret_key_here

# Nginx 配置
NGINX_PORT=8082
```

**重要提示**:
- 首次部署前，请修改 `MONGODB_PASSWORD`、`REDIS_PASSWORD`、`SECRET_KEY` 等敏感配置
- 生产环境部署时，务必使用强密码

---

## 🐛 故障排查

### 问题 1: Docker 未安装

**错误信息**:
```
❌ Docker 未安装，请先安装 Docker
```

**解决方法**:
- Linux: https://docs.docker.com/engine/install/
- macOS: https://docs.docker.com/desktop/install/mac-install/
- Windows: https://docs.docker.com/desktop/install/windows-install/

### 问题 2: 端口被占用

**错误信息**:
```
Error: Bind for 0.0.0.0:8082 failed: port is already allocated
```

**解决方法**:
1. 修改 `.env` 文件中的 `NGINX_PORT`
2. 或停止占用端口的服务

### 问题 3: 配置文件下载失败

**错误信息**:
```
❌ Nginx 配置文件下载失败
```

**解决方法**:
手动下载配置文件：
```bash
mkdir -p nginx
wget https://www.tradingagentscn.com/docker/nginx-proxy.conf -O nginx/nginx-proxy.conf
```

### 问题 4: 权限不足 (Linux)

**错误信息**:
```
Permission denied
```

**解决方法**:
```bash
# 赋予脚本执行权限
chmod +x deploy.sh

# 或使用 sudo 运行
sudo ./deploy.sh
```

---

## 📚 更多文档

- [Docker 部署文档](../docs/deployment/docker/DOCKER_DEPLOYMENT_v1.0.0.md)
- [数据库设计文档](../docs/design/v2.0/database-design.md)
- [API 文档](http://localhost:8082/api/docs) (部署后访问)

---

## 🆘 获取帮助

如果遇到问题，请：

1. 查看日志: `docker-compose -f docker-compose.compiled.yml logs -f`
2. 检查服务状态: `docker-compose -f docker-compose.compiled.yml ps`
3. 访问官方网站: https://www.tradingagentscn.com
4. 联系技术支持

---

**最后更新**: 2026-01-25  
**版本**: v1.0.0

