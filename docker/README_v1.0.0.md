# TradingAgents-CN Docker 部署指南 (v1.0.0)

## 📋 更新说明 (2026-01-21)

### 新增功能
- ✅ **Worker 服务**: 独立的分析任务处理容器
- ✅ **UTF-8 编码支持**: 解决中文字符显示问题  
- ✅ **运行时目录映射**: 支持 PID 文件和状态管理
- ✅ **启动脚本**: Windows (PowerShell) 和 Linux (Bash) 启动脚本
- ✅ **Core 模块**: 包含 v2.0 架构的核心功能
- ✅ **Prompts 目录**: 提示词模板支持

### 服务架构

```
TradingAgents-CN Docker Stack
├── backend (FastAPI)      - 后端 API 服务 (端口 8000)
├── worker (Python)        - 分析任务处理
├── frontend (Vue 3)       - 前端界面 (端口 3000)
├── mongodb (MongoDB 4.4)  - 数据库 (端口 27017)
├── redis (Redis 7)        - 缓存和消息队列 (端口 6379)
├── redis-commander        - Redis 管理界面 (端口 8081, 可选)
└── mongo-express          - MongoDB 管理界面 (端口 8082, 可选)
```

---

## 🚀 快速开始

### 方式 1: 使用启动脚本 (推荐)

**Windows (PowerShell)**:
```powershell
cd docker
.\start-docker.ps1
```

**Linux/Mac (Bash)**:
```bash
cd docker
chmod +x start-with-monitor.sh
./start-with-monitor.sh
```

### 方式 2: 使用 docker-compose 命令

```bash
# 启动所有服务
docker-compose up -d

# 启动并包含管理工具
docker-compose --profile management up -d

# 查看日志
docker-compose logs -f

# 停止所有服务
docker-compose down
```

---

## 📦 环境配置

### 1. 创建 .env 文件

如果没有 `.env` 文件，复制 `.env.docker`:

```bash
cp .env.docker .env
```

### 2. 配置环境变量

编辑 `.env` 文件，设置必要的 API 密钥：

```bash
# Tushare API Token (必需)
TUSHARE_TOKEN=your_tushare_token_here

# OpenAI API Key (可选)
OPENAI_API_KEY=your_openai_key_here

# 其他 LLM API Keys (可选)
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
```

---

## 🔧 服务管理

### 启动服务

```bash
# 启动所有核心服务
docker-compose up -d

# 启动并重新构建镜像
docker-compose up -d --build

# 启动特定服务
docker-compose up -d backend worker
```

### 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷 (⚠️ 会删除数据库数据)
docker-compose down -v
```

### 查看状态

```bash
# 查看所有服务状态
docker-compose ps

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f worker

# 查看最近 100 行日志
docker-compose logs --tail=100
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart backend
docker-compose restart worker
```

---

## 📊 服务访问

### 核心服务

| 服务 | URL | 说明 |
|------|-----|------|
| Backend API | http://localhost:8000 | FastAPI 后端服务 |
| Frontend | http://localhost:3000 | Vue 3 前端界面 |
| API Docs | http://localhost:8000/docs | Swagger API 文档 |
| MongoDB | mongodb://localhost:27017 | 数据库连接 |
| Redis | redis://localhost:6379 | 缓存连接 |

### 管理工具 (需要 --profile management)

| 工具 | URL | 用户名 | 密码 |
|------|-----|--------|------|
| Redis Commander | http://localhost:8081 | - | - |
| Mongo Express | http://localhost:8082 | admin | tradingagents123 |

---

## 🐛 故障排查

### 1. 服务无法启动

```bash
# 查看详细日志
docker-compose logs backend
docker-compose logs worker

# 检查容器状态
docker-compose ps

# 重新构建镜像
docker-compose build --no-cache
docker-compose up -d
```

### 2. 数据库连接失败

```bash
# 检查 MongoDB 健康状态
docker-compose exec mongodb mongo --eval "db.adminCommand('ping')"

# 检查 Redis 连接
docker-compose exec redis redis-cli ping
```

### 3. Worker 任务不执行

```bash
# 查看 Worker 日志
docker-compose logs -f worker

# 重启 Worker
docker-compose restart worker
```

### 4. 端口冲突

如果端口被占用，修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "8001:8000"  # 将 8000 改为 8001
```

---

## 📝 开发模式

### 挂载源代码进行开发

修改 `docker-compose.yml`，添加代码目录映射：

```yaml
volumes:
  - ./app:/app/app
  - ./core:/app/core
  - ./logs:/app/logs
```

然后重启服务：

```bash
docker-compose restart backend worker
```

---

## 🔐 安全建议

1. **修改默认密码**: 修改 `docker-compose.yml` 中的数据库密码
2. **使用环境变量**: 敏感信息存储在 `.env` 文件中
3. **限制端口暴露**: 生产环境中只暴露必要的端口
4. **定期备份**: 定期备份 MongoDB 和 Redis 数据

---

## 📚 相关文档

- [Docker 部署文档](../docs/deployment/docker/)
- [API 文档](http://localhost:8000/docs)
- [项目主 README](../README.md)

---

**最后更新**: 2026-01-21  
**版本**: v1.0.0

