# 演示系统部署完整指南

## 📋 概述

本文档提供在远程服务器上部署 TradingAgents 演示系统的完整步骤，包括：
- ✅ 从 Docker Hub 拉取镜像
- ✅ 配置环境变量
- ✅ 启动服务
- ✅ 导入配置数据
- ✅ 创建默认管理员账号

---

## 🎯 部署目标

部署一个包含完整配置的演示系统：
- ✅ 15 个 LLM 模型配置（Google Gemini、DeepSeek、百度千帆、阿里百炼、OpenRouter）
- ✅ 默认管理员账号（admin/admin123）
- ✅ 系统配置和用户标签
- ❌ 不包含历史数据（分析报告、股票数据等）

---

## 📦 前置要求

### 1. 服务器要求

| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| **CPU** | 2 核 | 4 核+ |
| **内存** | 4 GB | 8 GB+ |
| **磁盘** | 20 GB | 50 GB+ |
| **操作系统** | Linux (Ubuntu 20.04+, CentOS 7+) | Ubuntu 22.04 LTS |

### 2. 软件要求

- ✅ Docker (20.10+)
- ✅ Docker Compose (2.0+)
- ✅ Python 3.10+（用于导入脚本）
- ✅ Git（可选，用于克隆仓库）

### 3. 网络要求

- ✅ 能够访问 Docker Hub
- ✅ 开放端口：3000（前端）、8000（后端）

---

## 🚀 快速部署（5 分钟）

### 一键部署脚本

```bash
# 下载并运行部署脚本
curl -fsSL https://raw.githubusercontent.com/your-org/TradingAgents-CN/main/scripts/deploy_demo.sh | bash
```

### 手动部署步骤

如果需要更多控制，请按照以下详细步骤操作。

---

## 📖 详细部署步骤

### 步骤 1：安装 Docker 和 Docker Compose

#### Ubuntu/Debian

```bash
# 更新包索引
sudo apt-get update

# 安装依赖
sudo apt-get install -y ca-certificates curl gnupg

# 添加 Docker 官方 GPG 密钥
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 设置 Docker 仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
docker --version
docker compose version
```

#### CentOS/RHEL

```bash
# 安装依赖
sudo yum install -y yum-utils

# 添加 Docker 仓库
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 安装 Docker Engine
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
docker --version
docker compose version
```

#### 配置 Docker 权限

```bash
# 将当前用户添加到 docker 组
sudo usermod -aG docker $USER

# 重新登录或运行
newgrp docker

# 验证
docker ps
```

---

### 步骤 2：获取项目文件

#### 方法 1：克隆完整仓库（推荐）

```bash
# 克隆仓库
git clone https://github.com/your-org/TradingAgents-CN.git
cd TradingAgents-CN
```

#### 方法 2：只下载部署文件

```bash
# 创建项目目录
mkdir -p TradingAgents-Demo
cd TradingAgents-Demo

# 创建必要的目录
mkdir -p install scripts

# 下载 docker-compose 文件
curl -o docker-compose.hub.yml https://raw.githubusercontent.com/your-org/TradingAgents-CN/main/docker-compose.hub.yml

# 下载环境变量模板
curl -o .env.example https://raw.githubusercontent.com/your-org/TradingAgents-CN/main/.env.example

# 下载配置数据
curl -o install/database_export_config_2025-10-16.json https://raw.githubusercontent.com/your-org/TradingAgents-CN/main/install/database_export_config_2025-10-16.json

# 下载导入脚本
curl -o scripts/import_config_and_create_user.py https://raw.githubusercontent.com/your-org/TradingAgents-CN/main/scripts/import_config_and_create_user.py

# 复制环境变量文件
cp .env.example .env
```

---

### 步骤 3：配置环境变量

编辑 `.env` 文件：

```bash
nano .env
```

**必须修改的配置**：

```bash
# ==================== 基础配置 ====================
ENVIRONMENT=production

# 服务器地址（修改为您的服务器 IP 或域名）
SERVER_HOST=your-server-ip-or-domain

# ==================== 数据库配置 ====================
# MongoDB 密码（建议修改）
MONGO_PASSWORD=your-strong-password-here

# Redis 密码（建议修改）
REDIS_PASSWORD=your-strong-password-here

# ==================== 安全配置 ====================
# JWT 密钥（必须修改为随机字符串）
JWT_SECRET_KEY=your-random-secret-key-here
```

**生成随机密钥**：

```bash
# 生成 JWT 密钥
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 或使用 openssl
openssl rand -base64 32
```

**完整的 .env 示例**：

```bash
# ==================== 基础配置 ====================
ENVIRONMENT=production
SERVER_HOST=demo.tradingagents.cn
DEBUG=false

# ==================== 数据库配置 ====================
MONGO_HOST=mongodb
MONGO_PORT=27017
MONGO_DB=tradingagents
MONGO_USER=admin
MONGO_PASSWORD=MyStrongPassword123!
MONGO_URI=mongodb://admin:MyStrongPassword123!@mongodb:27017/tradingagents?authSource=admin

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=MyRedisPassword123!
REDIS_DB=0

# ==================== 安全配置 ====================
JWT_SECRET_KEY=xK9mP2vN8qR5tY7wZ3aB6cD1eF4gH0jL
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ==================== API 密钥（可选，导入后配置）====================
GOOGLE_API_KEY=
DEEPSEEK_API_KEY=
QIANFAN_ACCESS_KEY=
QIANFAN_SECRET_KEY=
DASHSCOPE_API_KEY=
OPENROUTER_API_KEY=
TUSHARE_TOKEN=
```

---

### 步骤 4：拉取 Docker 镜像

```bash
# 拉取镜像
docker compose -f docker-compose.hub.yml pull

# 查看拉取的镜像
docker images | grep tradingagents
```

**预期输出**：

```
hsliup/tradingagents-frontend   latest    xxx    xxx MB
hsliup/tradingagents-backend    latest    xxx    xxx MB
mongo                           4.4       xxx    xxx MB
redis                           7-alpine  xxx    xxx MB
```

---

### 步骤 5：启动服务

```bash
# 启动所有服务（首次启动会自动创建数据卷）
docker compose -f docker-compose.hub.yml up -d

# 查看服务状态
docker compose -f docker-compose.hub.yml ps
```

**注意**：首次启动时，Docker Compose 会自动创建以下数据卷：
- `tradingagents_mongodb_data` - MongoDB 数据存储
- `tradingagents_redis_data` - Redis 数据存储

**预期输出**：

```
NAME                     IMAGE                                STATUS
tradingagents-mongodb    mongo:4.4                            Up
tradingagents-redis      redis:7-alpine                       Up
tradingagents-backend    hsliup/tradingagents-backend:latest  Up
tradingagents-frontend   hsliup/tradingagents-frontend:latest Up
```

**等待服务启动**：

```bash
# 等待 MongoDB 启动（约 15 秒）
echo "等待 MongoDB 启动..."
sleep 15

# 检查 MongoDB 是否就绪
docker exec tradingagents-mongodb mongosh --eval "db.adminCommand('ping')" || \
docker exec tradingagents-mongodb mongo --eval "db.adminCommand('ping')"
```

---

### 步骤 6：安装 Python 依赖

```bash
# 安装 Python 3 和 pip
sudo apt-get install -y python3 python3-pip

# 安装 pymongo
pip3 install pymongo
```

---

### 步骤 7：导入配置数据并创建默认用户

```bash
# 运行导入脚本
python3 scripts/import_config_and_create_user.py
```

**预期输出**：

```
================================================================================
📦 导入配置数据并创建默认用户
================================================================================

💡 未指定文件，使用默认配置: install/database_export_config_2025-10-16.json

🔌 连接到 MongoDB...
✅ MongoDB 连接成功

📂 加载导出文件...
✅ 文件加载成功
   导出时间: 2025-10-16T10:30:00
   集合数量: 9

🚀 开始导入...
   ✅ system_configs: 插入 1 个
   ✅ users: 插入 3 个
   ✅ llm_providers: 插入 5 个
   ✅ model_catalog: 插入 15 个
   ...

📊 导入统计:
   插入: 48 个文档

👤 创建默认管理员用户...
✅ 管理员用户创建成功
   用户名: admin
   密码: admin123

================================================================================
✅ 操作完成！
================================================================================
```

---

### 步骤 8：重启后端服务

```bash
# 重启后端服务以加载配置
docker restart tradingagents-backend

# 等待后端启动
sleep 5

# 查看后端日志
docker logs tradingagents-backend --tail 30
```

**查找以下日志确认成功**：

```
✅ 配置桥接完成
✅ 已启用 15 个 LLM 配置
✅ 数据源配置已同步
```

---

### 步骤 9：验证部署

#### 1. 检查服务状态

```bash
# 查看所有容器
docker compose -f docker-compose.hub.yml ps

# 所有容器应该都是 Up 状态
```

#### 2. 测试后端 API

```bash
# 测试健康检查
curl http://localhost:8000/api/health

# 预期输出
{"status":"healthy","timestamp":"..."}
```

#### 3. 访问前端

在浏览器中访问：

```
http://your-server-ip:3000
```

#### 4. 登录系统

使用默认管理员账号：
- **用户名**：`admin`
- **密码**：`admin123`

#### 5. 验证配置

登录后检查：

1. **系统配置**：
   - 进入：`系统管理` → `系统配置`
   - 确认看到 15 个 LLM 模型配置

2. **数据库状态**：
   - 进入：`系统管理` → `数据库管理`
   - 确认 MongoDB 和 Redis 连接正常

---

## 🔧 常用管理命令

### 查看日志

```bash
# 查看所有服务日志
docker compose -f docker-compose.hub.yml logs -f

# 查看特定服务日志
docker logs tradingagents-backend -f
docker logs tradingagents-frontend -f
```

### 重启服务

```bash
# 重启所有服务
docker compose -f docker-compose.hub.yml restart

# 重启特定服务
docker restart tradingagents-backend
```

### 停止服务

```bash
# 停止所有服务
docker compose -f docker-compose.hub.yml stop

# 停止并删除容器
docker compose -f docker-compose.hub.yml down
```

### 更新镜像

```bash
# 拉取最新镜像
docker compose -f docker-compose.hub.yml pull

# 重新创建容器
docker compose -f docker-compose.hub.yml up -d --force-recreate
```

---

## 🐛 故障排除

### 问题 1：无法拉取 Docker 镜像

**解决方案**：配置镜像加速器

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
EOF

sudo systemctl daemon-reload
sudo systemctl restart docker
```

### 问题 2：MongoDB 连接失败

**解决方案**：

```bash
# 检查 MongoDB 状态
docker logs tradingagents-mongodb --tail 50

# 重启 MongoDB
docker restart tradingagents-mongodb
sleep 15
```

### 问题 3：前端无法访问

**解决方案**：

```bash
# 检查防火墙
sudo ufw allow 3000/tcp
sudo ufw allow 8000/tcp

# 重启前端
docker restart tradingagents-frontend
```

### 问题 4：导入脚本失败

**解决方案**：

```bash
# 安装依赖
pip3 install pymongo

# 检查配置文件
ls -lh install/database_export_config_*.json

# 手动指定文件
python3 scripts/import_config_and_create_user.py install/database_export_config_2025-10-16.json
```

---

## 🔒 安全加固

### 1. 修改默认密码

**修改管理员密码**：
1. 登录系统
2. 进入：`个人中心` → `修改密码`
3. 输入新密码并保存

### 2. 配置防火墙

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 3000/tcp  # 前端
sudo ufw allow 8000/tcp  # 后端
sudo ufw enable
```

### 3. 配置 HTTPS（推荐）

```bash
# 安装 Nginx 和 Certbot
sudo apt-get install -y nginx certbot python3-certbot-nginx

# 配置 Nginx 反向代理
sudo nano /etc/nginx/sites-available/tradingagents

# 获取 SSL 证书
sudo certbot --nginx -d your-domain.com

# 重启 Nginx
sudo systemctl restart nginx
```

---

## 📝 部署检查清单

- [ ] Docker 和 Docker Compose 已安装
- [ ] 所有容器正在运行（4 个）
- [ ] MongoDB 连接正常
- [ ] Redis 连接正常
- [ ] 配置数据已导入（48 个文档）
- [ ] 默认管理员账号已创建
- [ ] 前端可以访问
- [ ] 后端 API 可以访问
- [ ] 可以使用 admin/admin123 登录
- [ ] 系统配置显示 15 个 LLM 模型
- [ ] 已修改默认密码
- [ ] 防火墙已配置

---

## 🎉 部署完成

恭喜！您已成功部署 TradingAgents 演示系统！

**登录信息**：
- 用户名：`admin`
- 密码：`admin123`
- 前端地址：`http://your-server:3000`
- 后端地址：`http://your-server:8000`

**下一步**：
1. ⚠️ 立即修改默认密码
2. 配置 LLM API 密钥
3. 测试股票分析功能
4. 邀请用户体验

---

## 📚 相关文档

- [导出配置数据](./export_config_for_demo.md)
- [使用脚本导入配置](./import_config_with_script.md)
- [Docker 数据卷管理](./docker_volumes_unified.md)

