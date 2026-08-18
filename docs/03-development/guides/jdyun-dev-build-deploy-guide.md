# 京东云版开发测试与打包部署指南

> 本文档面向开发维护人员，描述京东云合作版的完整开发、测试、打包、部署流程。

---

## 1. 环境准备

### 1.1 开发环境

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11（开发），Linux（生产） |
| Python | 3.11.9（项目 `env/` 虚拟环境） |
| Node.js | 18+（前端构建） |
| Docker Desktop | 最新版（构建镜像） |
| Git | 分支 `release/jdyun-v3.0` |

### 1.2 关键目录

```
TradingAgentsCN/
├── app/                    # 后端 FastAPI
├── core/                   # 核心库（LLM、向量库、知识库）
├── frontend/               # 前端 Vue3 + Vite
├── deploy-all-in-one/      # 单容器部署（Dockerfile、build.sh、run.sh）
├── docs/                   # 文档
├── env/                    # Python 虚拟环境
├── start_dev.ps1           # 开发环境启动脚本
└── VERSION                 # 版本号
```

### 1.3 京东云版与普通版的区别

| 区别点 | 普通版 | 京东云版 |
|--------|--------|---------|
| 认证方式 | 用户名密码 | Basic Auth（网关注入） |
| LLM 服务 | 用户自配 | 京东云模型服务 |
| Embedding | 用户自配 | 京东云 Embedding 服务 |
| 数据源 | 用户自配 | 预配 Tushare |
| 环境文件 | `.env.docker` | `.env.docker.jdyun` |
| 镜像 Tag | `3.0.0` | `3.0.0-jdyun` |
| MongoDB 数据卷 | `ta-mongo-data` | `ta-data` |

---

## 2. 本地开发测试

### 2.1 配置文件

编辑 `deploy-all-in-one/.env.docker.jdyun`：

```bash
# 京东云模式
JDYUN_MODE=true

# Basic Auth 白名单（模拟京东云网关注入的凭据）
JDYUN_BASIC_AUTH_USERS=jcloud-ugidvcp:8437F13DABE87D0BC1D4DCCD4739C5A7

# LLM 配置
OPENAI_API_BASE=https://modelservice.jdcloud.com/v1
OPENAI_API_KEY=<京东云API Key>
OPENAI_MODEL=GLM-5

# Embedding 配置
EMBEDDING_API_BASE=https://modelservice.jdcloud.com/v1
EMBEDDING_API_KEY=<京东云API Key>
EMBEDDING_MODEL=Qwen3-Embedding-8B

# 数据源
TUSHARE_TOKEN=<Tushare Token>

# MongoDB
MONGODB_PASSWORD=<自定义密码>

# 安全配置（可选，容器自动生成）
# JWT_SECRET / CSRF_SECRET

# IP 白名单（本地开发设置）
JDYUN_GATEWAY_IPS=127.0.0.1,::1
```

### 2.2 启动单容器（本地开发）

```powershell
# 构建镜像（首次或代码变更后）
bash deploy-all-in-one/build.sh 3.0.0 --jdyun --single-arch

# 启动容器
bash deploy-all-in-one/run.sh --jdyun

# 开发模式（挂载本地代码，改代码后 --restart-be 秒级生效）
bash deploy-all-in-one/run.sh --jdyun --dev
```

### 2.3 启动模拟网关（前端测试）

模拟网关模拟京东云网关行为，提供登录页 + Basic Auth 注入：

```powershell
# 启动模拟网关
node frontend/mock-jdyun-gateway.mjs
```

模拟网关配置：
- 网关地址：`http://localhost:3100`
- 登录凭据：`testuser` / `Test@123456`（写死在代码中）
- 目标地址：`http://127.0.0.1:8082`（单容器 Nginx）
- 注入的 Basic Auth：从 `JDYUN_INJECT_AUTH` 环境变量读取，默认为 `.env.docker.jdyun` 中的凭据

### 2.4 验证测试

**浏览器测试**：
1. 打开 `http://localhost:3100`
2. 输入 `testuser` / `Test@123456`
3. 登录后应直接进入仪表板（不出现登录页）

**API 测试**：

```bash
# 新用户首次认证（严格校验）
curl -u "jcloud-ugidvcp:8437F13DABE87D0BC1D4DCCD4739C5A7" http://127.0.0.1:8082/api/auth/me

# 老用户免令牌（token 可变）
curl -u "jcloud-ugidvcp:AnyToken" http://127.0.0.1:8082/api/auth/me

# 伪造用户被拒绝
curl -u "fake-user:anything" http://127.0.0.1:8082/api/auth/me  # 401
```

**健康检查**：
```bash
curl http://127.0.0.1:8082/api/health
curl http://127.0.0.1:8082/nginx-health
```

### 2.5 开发模式常用操作

```powershell
# 查看日志
bash deploy-all-in-one/run.sh --logs

# 重启后端（改代码后）
bash deploy-all-in-one/run.sh --restart-be

# 进入容器 shell
bash deploy-all-in-one/run.sh --shell

# 查看容器状态
bash deploy-all-in-one/run.sh --status

# 停止容器
bash deploy-all-in-one/run.sh --stop

# 清理所有数据卷（危险！）
bash deploy-all-in-one/run.sh --clean
```

---

## 3. 打包生产镜像

### 3.1 前置准备

1. 确认分支：`git checkout release/jdyun-v3.0`
2. 确认代码已提交：`git status`
3. 确认版本号：`cat VERSION`
4. 前端构建产物已更新：`frontend/dist/` 目录存在且为最新

### 3.2 前端构建

```powershell
cd frontend
npm install
npm run build
cd ..
```

### 3.3 构建镜像

```powershell
# 构建京东云版镜像（单架构，推送用）
bash deploy-all-in-one/build.sh 3.0.0 --jdyun --single-arch

# 构建普通版镜像（对比测试用）
bash deploy-all-in-one/build.sh 3.0.0 --single-arch
```

构建参数说明：
- `3.0.0`：版本号（对应 VERSION 文件）
- `--jdyun`：京东云版（追加 `-jdyun` 后缀到 tag）
- `--single-arch`：只构建 x86_64（京东云服务器架构）
- `--skip-frontend`：跳过前端构建（已手动构建时使用）

### 3.4 验证镜像

```powershell
# 查看镜像
docker images tradingagents-cn-pro --format "table {{.Repository}}:{{.Tag}}\t{{.CreatedAt}}\t{{.Size}}"

# 检查镜像内容
docker run --rm tradingagents-cn-pro:3.0.0-jdyun ls /app/docs/02-user-guide/
docker run --rm tradingagents-cn-pro:3.0.0-jdyun ls /app/qdrant-seed/
docker run --rm tradingagents-cn-pro:3.0.0-jdyun cat /app/VERSION

# 快速启动测试
bash deploy-all-in-one/run.sh --jdyun
# 等待 30 秒后访问 http://localhost:8082
```

### 3.5 镜像内置内容

| 内容 | 路径 | 说明 |
|------|------|------|
| 前端构建产物 | `/app/frontend/dist/` | Vite 编译的静态文件 |
| 后端代码 | `/app/app/`, `/app/core/` | FastAPI 应用 |
| 用户手册 | `/app/docs/02-user-guide/` | 内置文档文件 |
| 预生成向量索引 | `/app/qdrant-seed/` | Qdrant 种子数据（首次部署零等待） |
| MongoDB 7.0 | `/usr/local/bin/mongod` | 数据库 |
| Redis 7 | `/usr/local/bin/redis-server` | 缓存 |
| Nginx | `/usr/sbin/nginx` | 反向代理 |
| s6-overlay | `/init` | 进程管理 |

---

## 4. 推送到京东云仓库

### 4.1 登录京东云镜像仓库

```powershell
docker login agentengine-tradingagent-cn-north-1.jcr.service.jdcloud.com
# 输入京东云提供的账号密码
```

### 4.2 打 Tag 并推送

```powershell
# 打 Tag
docker tag tradingagents-cn-pro:3.0.0-jdyun `
  agentengine-tradingagent-cn-north-1.jcr.service.jdcloud.com/tradingagent:3.0.0-jdyun

# 推送
docker push agentengine-tradingagent-cn-north-1.jcr.service.jdcloud.com/tradingagent:3.0.0-jdyun
```

### 4.3 常见推送问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 502 Bad Gateway | 京东云服务端临时故障 | 重试推送（大部分 layer 已在远程，重试很快） |
| 401 Unauthorized | 未登录或登录过期 | 重新 `docker login` |
| 网络超时 | 镜像较大（5.4GB） | 确保网络稳定，耐心等待 |

推送失败后重试示例：
```powershell
# 重试（大部分 layer 已存在，只需推送 manifest）
docker push agentengine-tradingagent-cn-north-1.jcr.service.jdcloud.com/tradingagent:3.0.0-jdyun
# 看到 "Layer already exists" 表示之前已推送成功
# 最后出现 "digest: sha256:..." 表示推送完成
```

---

## 5. 京东云侧部署

### 5.1 docker-compose 部署（推荐）

京东云工程师使用以下文件部署：

**docker-compose.yml**：
```yaml
services:
  tradingagents:
    image: agentengine-tradingagent-cn-north-1.jcr.service.jdcloud.com/tradingagent:3.0.0-jdyun
    container_name: tradingagents-jdyun
    hostname: tradingagents
    restart: unless-stopped
    ports:
      - "${HOST_PORT:-8082}:8082"
    volumes:
      - ta-data:/data/db
      - ta-redis:/var/lib/redis
      - ta-runtime:/app/runtime
      - ta-logs:/app/logs
      - ta-qdrant:/app/data
    environment:
      TZ: "Asia/Shanghai"
      MONGODB_PASSWORD: "${MONGODB_PASSWORD}"
      JDYUN_MODE: "true"
      OPENAI_API_BASE: "${OPENAI_API_BASE:-https://modelservice.jdcloud.com/v1}"
      OPENAI_API_KEY: "${OPENAI_API_KEY}"
      OPENAI_MODEL: "${OPENAI_MODEL:-GLM-5}"
      EMBEDDING_API_BASE: "${EMBEDDING_API_BASE:-https://modelservice.jdcloud.com/v1}"
      EMBEDDING_API_KEY: "${EMBEDDING_API_KEY}"
      EMBEDDING_MODEL: "${EMBEDDING_MODEL:-Qwen3-Embedding-8B}"
      TUSHARE_TOKEN: "${TUSHARE_TOKEN}"
      JDYUN_BASIC_AUTH_USERS: "${JDYUN_BASIC_AUTH_USERS}"
      JDYUN_GATEWAY_IPS: "${JDYUN_GATEWAY_IPS}"
      JDYUN_LLM_MAX_RETRIES: "${JDYUN_LLM_MAX_RETRIES:-8}"
      JDYUN_LLM_MAX_RPM: "${JDYUN_LLM_MAX_RPM:-30}"
      JDYUN_BATCH_MAX_CONCURRENT: "${JDYUN_BATCH_MAX_CONCURRENT:-1}"
      JDYUN_WORKER_MAX_CONCURRENT: "${JDYUN_WORKER_MAX_CONCURRENT:-1}"
      JDYUN_STOCK_INTERVAL_SECONDS: "${JDYUN_STOCK_INTERVAL_SECONDS:-10}"

volumes:
  ta-data:
    driver: local
  ta-redis:
    driver: local
  ta-runtime:
    driver: local
  ta-logs:
    driver: local
  ta-qdrant:
    driver: local
```

**.env**：
```bash
# 必填
MONGODB_PASSWORD=<自定义密码>
OPENAI_API_KEY=<京东云API Key>
EMBEDDING_API_KEY=<京东云API Key>
JDYUN_BASIC_AUTH_USERS=<username>:<token>
TUSHARE_TOKEN=<用户的Tushare Token>

# 推荐
JDYUN_GATEWAY_IPS=<京东云网关IP>

# 可选（容器自动生成）
# JWT_SECRET / CSRF_SECRET

# 可选（有默认值）
HOST_PORT=8082
OPENAI_MODEL=GLM-5
EMBEDDING_MODEL=Qwen3-Embedding-8B
```

### 5.2 数据卷说明

| 卷名 | 容器路径 | 用途 | 重要性 |
|------|---------|------|--------|
| `ta-data` | `/data/db` | MongoDB 数据 | 🔴 用户数据、任务、报告 |
| `ta-redis` | `/var/lib/redis` | Redis 数据 | 🟡 缓存、队列（可重建） |
| `ta-runtime` | `/app/runtime` | 运行时配置、密钥 | 🔴 JWT/CSRF 密钥持久化 |
| `ta-logs` | `/app/logs` | 日志 | 🟢 可清理 |
| `ta-qdrant` | `/app/data` | Qdrant 向量数据 | 🔴 向量索引持久化 |

> **容器删除重建后，只要数据卷保留，用户数据和索引都不会丢失。**

### 5.3 验证部署

```bash
# 启动
docker-compose up -d

# 等待 30 秒
sleep 30

# 健康检查
curl http://localhost:8082/nginx-health

# 认证验证（替换实际凭据）
curl -u "<username>:<token>" http://localhost:8082/api/auth/me

# 预期返回
# {"success":true,"data":{"username":"...","is_admin":true,"auth_method":"basic","provider":"jdyun"}}
```

---

## 6. 镜像更新流程

当代码有更新需要重新发布时：

```
1. 开发测试（本地验证通过）
   ↓
2. 构建新镜像
   bash deploy-all-in-one/build.sh 3.0.0 --jdyun --single-arch
   ↓
3. 本地验证新镜像
   bash deploy-all-in-one/run.sh --jdyun
   访问 http://localhost:8082 验证功能
   ↓
4. 推送到京东云
   docker tag ... :3.0.0-jdyun
   docker push ...
   ↓
5. 通知京东云工程师
   docker-compose pull && docker-compose up -d
   （数据卷保留，用户数据不丢失）
```

---

## 7. 向量索引种子数据维护

### 7.1 种子数据的作用

镜像内置预生成的向量索引（用户手册 + 能力索引），首次部署时无需等待 embedding 请求，秒级可用。

### 7.2 何时需要更新种子数据

| 场景 | 需要更新 | 说明 |
|------|---------|------|
| 用户手册内容变更 | ✅ | 需重新生成种子 |
| Embedding 模型变更 | ✅ | 维度不同，需重建 |
| 代码逻辑变更（不影响索引内容） | ❌ | 签名比对仍会跳过 |
| 新增工具/Skill/Agent | ✅ | 能力索引需更新 |

### 7.3 重新生成种子数据

```powershell
# 1. 启动容器，确保 embedding 可用，索引构建完成
bash deploy-all-in-one/run.sh --jdyun

# 2. 等待索引构建完成（查看日志）
bash deploy-all-in-one/run.sh --logs
# 等待 "用户手册索引构建完成" 或 "跳过重建" 日志

# 3. 导出种子数据
docker exec tradingagents bash -c "cp -r /app/data/qdrant/* /app/qdrant-seed/"

# 4. 拷贝到本地
docker cp tradingagents:/app/qdrant-seed/ deploy-all-in-one/qdrant-seed/

# 5. 重新构建镜像
bash deploy-all-in-one/build.sh 3.0.0 --jdyun --single-arch

# 6. 验证：清理 Qdrant 卷后启动，确认种子导入 + 签名跳过
bash deploy-all-in-one/run.sh --clean
bash deploy-all-in-one/run.sh --jdyun
# 日志应显示 "导入预生成的向量索引种子数据" + "跳过重建（签名一致）"
```

### 7.4 签名比对机制

用户手册索引使用内容 hash 签名（基于文件内容 SHA-256 + 排序），确保跨环境一致：

```
首次部署：init 脚本从种子复制 → 后端检测签名一致 → 跳过重建 → 零 embedding 请求
后续重启：卷有数据 → 后端检测签名一致 → 跳过重建
手册更新：卷有数据 → 后端检测签名不一致 → 全量重建（仅这一次）
```

---

## 8. 故障排查

### 8.1 启动后 502 Bad Gateway

| 原因 | 检查 | 解决 |
|------|------|------|
| 后端还在启动 | `docker logs tradingagents` | 等待 30 秒 |
| MongoDB 启动失败 | 日志中搜索 `mongod` | 检查数据卷权限 |
| 后端代码报错 | 日志中搜索 `Traceback` | 查看具体错误 |

### 8.2 登录失败

| 原因 | 检查 | 解决 |
|------|------|------|
| Basic Auth 凭据不匹配 | 检查 `JDYUN_BASIC_AUTH_USERS` | 确认格式 `username:token` |
| IP 白名单拒绝 | 日志搜索 `403` | 添加客户端 IP 到 `JDYUN_GATEWAY_IPS` |
| 数据库被清空 | 新用户首次认证需要正确 token | 确认 token 与环境变量一致 |

### 8.3 向量索引问题

| 原因 | 检查 | 解决 |
|------|------|------|
| 索引每次重建 | 日志搜索 "签名" | 检查 Qdrant 数据卷是否持久化 |
| 问答机器人不可用 | 日志搜索 "embedding" | 检查 Embedding API Key 和地址 |
| 索引种子未导入 | 日志搜索 "种子" | 检查镜像是否包含 `/app/qdrant-seed/` |

### 8.4 LLM API 限速

京东云 API 有限速，已内置限速配置：

```bash
# 调整限速参数
JDYUN_LLM_MAX_RETRIES=8      # 最大重试次数
JDYUN_LLM_MAX_RPM=30        # 每分钟最大请求数
JDYUN_BATCH_MAX_CONCURRENT=1 # 批量并发数
JDYUN_WORKER_MAX_CONCURRENT=1 # Worker 并发数
JDYUN_STOCK_INTERVAL_SECONDS=10 # 股票分析间隔
```

---

## 9. 关键文件索引

| 文件 | 职责 |
|------|------|
| `deploy-all-in-one/Dockerfile` | 单容器镜像构建 |
| `deploy-all-in-one/build.sh` | 镜像构建脚本 |
| `deploy-all-in-one/run.sh` | 容器启动/管理脚本 |
| `deploy-all-in-one/docker-compose.yml` | 京东云部署 compose 文件 |
| `deploy-all-in-one/.env.docker.jdyun` | 京东云版环境配置 |
| `deploy-all-in-one/s6-rc.d/` | s6-overlay 服务定义 |
| `deploy-all-in-one/qdrant-seed/` | 预生成向量索引种子数据 |
| `frontend/mock-jdyun-gateway.mjs` | 模拟京东云网关（测试用） |
| `app/core/jdyun.py` | 京东云认证逻辑（白名单、IP 校验） |
| `app/services/user_service.py` | 京东云用户建档 |
| `app/routers/auth_db.py` | 认证路由（Basic Auth 接入） |
| `app/services/jdyun_init.py` | 京东云启动初始化 |
| `app/main.py` | 后端入口（异步索引、生命周期管理） |
| `core/knowledge/user_manual_manager.py` | 用户手册索引管理 |
| `core/memory/qdrant_adapter.py` | Qdrant 向量数据库适配器 |

---

## 10. 变更记录

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-08-02 | 初始版本，包含开发测试、打包部署、种子维护、故障排查 | hsliuping |
