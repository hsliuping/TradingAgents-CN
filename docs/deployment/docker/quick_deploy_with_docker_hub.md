# 🚀 TradingAgents-CN 快速部署指南（Docker Hub 镜像）

> 5 分钟快速部署完整的 AI 股票分析系统

## 📋 前置要求

- **Docker**: 20.10+ 
- **Docker Compose**: 2.0+
- **内存**: 4GB+（推荐 8GB+）
- **磁盘**: 20GB+

验证安装：
```bash
docker --version
docker-compose --version
```

---

## 🎯 部署步骤

### 步骤 1：下载部署文件

创建项目目录并下载必要文件：

```bash
# 创建项目目录
mkdir -p ~/tradingagents-demo
cd ~/tradingagents-demo

# 下载 Docker Compose 配置文件
wget https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/docker-compose.hub.nginx.yml

# 下载环境配置模板
wget https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/.env.docker -O .env

# 下载 Nginx 配置文件
mkdir -p nginx
wget https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/nginx/nginx.conf -O nginx/nginx.conf
```

**Windows PowerShell**：
```powershell
# 创建项目目录
New-Item -ItemType Directory -Path "$env:USERPROFILE\tradingagents-demo" -Force
Set-Location "$env:USERPROFILE\tradingagents-demo"

# 下载 Docker Compose 配置
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/docker-compose.hub.nginx.yml" -OutFile "docker-compose.hub.nginx.yml"

# 下载环境配置
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/.env.docker" -OutFile ".env"

# 下载 Nginx 配置
New-Item -ItemType Directory -Path "nginx" -Force
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/nginx/nginx.conf" -OutFile "nginx\nginx.conf"
```

### 步骤 2：拉取 Docker 镜像

```bash
# 拉取所有镜像（约 2-5 分钟，取决于网络速度）
docker-compose -f docker-compose.hub.nginx.yml pull
```

**预期输出**：
```
[+] Pulling 5/5
 ✔ mongodb Pulled
 ✔ redis Pulled
 ✔ backend Pulled
 ✔ frontend Pulled
 ✔ nginx Pulled
```

### 步骤 3：配置环境变量

编辑 `.env` 文件，配置至少一个 AI 模型的 API 密钥：

```bash
# Linux/macOS
nano .env

# Windows
notepad .env
```

**必需配置**（至少配置一个）：

```bash
# 阿里百炼（推荐，国产模型，中文优化）
DASHSCOPE_API_KEY=sk-your-dashscope-api-key-here
DASHSCOPE_ENABLED=true

# 或 DeepSeek（推荐，性价比高）
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
DEEPSEEK_ENABLED=true

# 或 OpenAI（需要国外网络）
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_ENABLED=true
```

**可选配置**：

```bash
# Tushare 数据源（专业金融数据，需要注册 https://tushare.pro）
TUSHARE_TOKEN=your-tushare-token-here
TUSHARE_ENABLED=true
TUSHARE_UNIFIED_ENABLED=true
TUSHARE_BASIC_INFO_SYNC_ENABLED=true
TUSHARE_QUOTES_SYNC_ENABLED=true
TUSHARE_HISTORICAL_SYNC_ENABLED=true
TUSHARE_FINANCIAL_SYNC_ENABLED=true

# 其他 AI 模型
QIANFAN_API_KEY=your-qianfan-api-key-here  # 百度文心一言
QIANFAN_ENABLED=true

GOOGLE_API_KEY=your-google-api-key-here    # Google Gemini
GOOGLE_ENABLED=true
```

**获取 API 密钥**：

| 服务 | 注册地址 | 说明 |
|------|---------|------|
| 阿里百炼 | https://dashscope.aliyun.com/ | 国产模型，中文优化，推荐 |
| DeepSeek | https://platform.deepseek.com/ | 性价比高，推荐 |
| OpenAI | https://platform.openai.com/ | 需要国外网络 |
| Tushare | https://tushare.pro/register?reg=tacn | 专业金融数据（可选） |

### 步骤 4：启动服务

```bash
# 启动所有服务（后台运行）
docker-compose -f docker-compose.hub.nginx.yml up -d

# 查看服务状态
docker-compose -f docker-compose.hub.nginx.yml ps
```

**预期输出**：
```
NAME                       IMAGE                                    STATUS
tradingagents-backend      hsliup/tradingagents-backend:latest      Up (healthy)
tradingagents-frontend     hsliup/tradingagents-frontend:latest     Up (healthy)
tradingagents-mongodb      mongo:4.4                                Up (healthy)
tradingagents-nginx        nginx:alpine                             Up
tradingagents-redis        redis:7-alpine                           Up (healthy)
```

**查看启动日志**（可选）：
```bash
# 查看所有服务日志
docker-compose -f docker-compose.hub.nginx.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.hub.nginx.yml logs -f backend
```

### 步骤 5：导入初始配置

**首次部署必须执行此步骤**，导入系统配置和创建管理员账号：

```bash
# 导入镜像内置的配置数据（推荐）
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py
```

**预期输出**：
```
💡 未指定文件，使用默认配置: /app/install/database_export_config_2025-10-17.json
================================================================================
📦 导入配置数据并创建默认用户
================================================================================

🔌 连接到 MongoDB...
✅ MongoDB 连接成功

📂 加载导出文件: /app/install/database_export_config_2025-10-17.json
✅ 文件加载成功
   导出时间: 2025-10-17T05:50:07
   集合数量: 11

📋 准备导入 11 个集合:
   - system_configs: 79 个文档
   - users: 1 个文档
   - llm_providers: 8 个提供商
   - model_catalog: 15+ 个模型
   - market_categories: 3 个分类
   - user_tags: 2 个标签
   - datasource_groupings: 3 个分组
   - platform_configs: 4 个配置
   - user_configs: 0 个配置
   - market_quotes: 5760 条行情数据
   - stock_basic_info: 5684 条股票信息

🚀 开始导入...
   ✅ 导入成功

👤 创建默认管理员用户...
   ✅ 用户创建成功

================================================================================
✅ 操作完成！
================================================================================

🔐 登录信息:
   用户名: admin
   密码: admin123
```

**说明**：
- ✅ 配置数据已打包到 Docker 镜像中（`/app/install/database_export_config_2025-10-17.json`）
- ✅ 脚本会自动检测并导入镜像内置的配置文件
- ✅ 导入的配置包含：
  - 系统配置（79 个配置项）
  - LLM 提供商配置（8 个提供商）
  - LLM 模型目录（15+ 个模型）
  - 市场分类、用户标签、数据源分组等
  - 示例股票数据（5000+ 条）
- ⚠️ 如果看到重复键错误（E11000），说明数据已存在，可以忽略

**预期输出（完整导入）**：
```
================================================================================
📦 导入配置数据并创建默认用户
================================================================================

💡 未指定文件，使用默认配置: /app/install/database_export_config.json

🔌 连接到 MongoDB...
✅ MongoDB 连接成功

📂 加载导出文件: /app/install/database_export_config.json
✅ 文件加载成功
   导出时间: 2025-10-17T05:50:07
   集合数量: 11

📋 准备导入 11 个集合:
   - system_configs: 79 个文档
   - users: 1 个文档
   - llm_providers: 8 个文档
   - market_categories: 3 个文档
   - user_tags: 2 个文档
   - datasource_groupings: 3 个文档
   - platform_configs: 4 个文档
   - model_catalog: 8 个文档
   - market_quotes: 5760 个实时行情数据
   - stock_basic_info: 5684 个股票基础信息

🚀 开始导入...
   ✅ 导入成功

👤 创建默认管理员用户...
   ✅ 用户创建成功

================================================================================
✅ 操作完成！
================================================================================

🔐 登录信息:
   用户名: admin
   密码: admin123
```

**预期输出（仅创建用户）**：
```
================================================================================
📦 创建默认管理员用户
================================================================================

🔌 连接到 MongoDB...
✅ MongoDB 连接成功

👤 创建默认管理员用户...
   ✅ 用户创建成功

================================================================================
✅ 操作完成！
================================================================================

🔐 登录信息:
   用户名: admin
   密码: admin123
```

### 步骤 6：重启后端服务

导入配置后，需要重启后端服务以加载新配置：

```bash
docker restart tradingagents-backend

# 等待服务重启（约 10-20 秒）
docker logs -f tradingagents-backend
```

看到以下日志表示启动成功：
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

按 `Ctrl+C` 退出日志查看。

### 步骤 7：访问系统

打开浏览器，访问：

```
http://你的服务器IP
```

**本地部署**：
```
http://localhost
```

**默认登录信息**：
- 用户名：`admin`
- 密码：`admin123`

**首次登录后建议**：
1. 修改默认密码（右上角用户菜单 → 个人设置）
2. 检查 LLM 配置（系统管理 → LLM 配置）
3. 测试运行一个简单的分析任务

---

## 🏗️ 部署架构

```
用户浏览器
    ↓
http://服务器IP:80
    ↓
┌─────────────────────────────────────┐
│  Nginx (统一入口)                    │
│  - 前端静态资源 (/)                  │
│  - API 反向代理 (/api → backend)    │
└─────────────────────────────────────┘
    ↓                    ↓
Frontend            Backend
(Vue 3)            (FastAPI)
    ↓                    ↓
                ┌────────┴────────┐
                ↓                 ↓
            MongoDB            Redis
          (数据存储)         (缓存)
```

**优势**：
- ✅ 统一入口，无跨域问题
- ✅ 便于配置 HTTPS
- ✅ 可添加负载均衡、缓存等功能

---

## 📁 目录结构

```
~/tradingagents-demo/
├── docker-compose.hub.nginx.yml  # Docker Compose 配置文件
├── .env                          # 环境变量配置
├── nginx/
│   └── nginx.conf                # Nginx 配置文件
├── logs/                         # 日志目录（自动创建）
├── data/                         # 数据目录（自动创建）
└── config/                       # 配置目录（自动创建）
```

**注意**：配置数据（`database_export_config_2025-10-17.json`）已打包到 Docker 镜像中，无需单独下载。

---

## 🔧 常见问题

### 1. 服务启动失败

**问题**：`docker-compose up` 报错

**解决方案**：

```bash
# 查看详细日志
docker-compose -f docker-compose.hub.nginx.yml logs

# 查看特定服务日志
docker-compose -f docker-compose.hub.nginx.yml logs backend

# 重启服务
docker-compose -f docker-compose.hub.nginx.yml restart
```

### 2. 无法访问系统

**问题**：浏览器无法打开 `http://服务器IP`

**检查清单**：

```bash
# 1. 检查服务状态
docker-compose -f docker-compose.hub.nginx.yml ps

# 2. 检查端口占用
sudo netstat -tulpn | grep :80

# 3. 检查防火墙（Linux）
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS

# 4. 开放 80 端口
sudo ufw allow 80  # Ubuntu
sudo firewall-cmd --add-port=80/tcp --permanent && sudo firewall-cmd --reload  # CentOS
```

### 3. API 请求失败

**问题**：前端显示"网络错误"或"API 请求失败"

**解决方案**：

```bash
# 检查后端日志
docker logs tradingagents-backend

# 检查 Nginx 日志
docker logs tradingagents-nginx

# 测试后端健康检查
curl http://localhost:8000/api/health
```

### 4. 数据库连接失败

**问题**：后端日志显示"MongoDB connection failed"

**解决方案**：

```bash
# 检查 MongoDB 状态
docker exec -it tradingagents-mongodb mongo -u admin -p tradingagents123 --authenticationDatabase admin

# 重启 MongoDB
docker-compose -f docker-compose.hub.nginx.yml restart mongodb

# 检查数据卷
docker volume inspect tradingagents_mongodb_data
```

### 5. 配置导入时出现重复键错误

**问题**：导入配置时 `market_quotes` 或 `stock_basic_info` 报错 `E11000 duplicate key error`

**解答**：这是正常的！说明数据库中已经有数据了。配置数据（LLM 配置、用户等）已经成功导入，系统可以正常使用。

如果确实想完全覆盖数据，可以使用：
```bash
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py --overwrite
```

---

## 🎓 进阶操作

### 更新系统

```bash
# 拉取最新镜像
docker-compose -f docker-compose.hub.nginx.yml pull

# 重启服务
docker-compose -f docker-compose.hub.nginx.yml up -d
```

### 备份数据

```bash
# 导出 MongoDB 数据
docker exec tradingagents-mongodb mongodump \
  -u admin -p tradingagents123 --authenticationDatabase admin \
  -d tradingagents -o /data/backup

# 复制备份到宿主机
docker cp tradingagents-mongodb:/data/backup ./mongodb_backup
```

### 查看系统状态

```bash
# 查看所有容器状态
docker-compose -f docker-compose.hub.nginx.yml ps

# 查看资源使用
docker stats

# 查看日志
docker-compose -f docker-compose.hub.nginx.yml logs -f --tail=100
```

### 停止服务

```bash
# 停止所有服务
docker-compose -f docker-compose.hub.nginx.yml down

# 停止并删除数据卷（⚠️ 会删除所有数据）
docker-compose -f docker-compose.hub.nginx.yml down -v
```

---

## 🆘 获取帮助

- **GitHub Issues**: https://github.com/hsliuping/TradingAgents-CN/issues
- **文档**: https://github.com/hsliuping/TradingAgents-CN/tree/v1.0.0-preview/docs
- **示例**: https://github.com/hsliuping/TradingAgents-CN/tree/v1.0.0-preview/examples

---

## 📝 总结

通过本指南，你应该能够：

✅ 在 5 分钟内完成系统部署  
✅ 配置 AI 模型和数据源  
✅ 成功访问和使用系统  
✅ 解决常见部署问题  

**下一步**：
1. 探索系统功能，运行第一个股票分析
2. 配置更多 AI 模型，对比分析效果
3. 自定义分析策略和参数
4. 集成到你的投资决策流程

祝你使用愉快！🎉

