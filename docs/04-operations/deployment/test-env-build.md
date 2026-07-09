# 测试环境镜像打包与部署指南

本文档介绍如何使用 `build-test-env.ps1` 脚本一键构建 Docker 镜像并启动测试环境。

## 前提条件

- Windows 10/11 + PowerShell 5.1+
- Docker Desktop（已启动，分配 4GB+ 内存）
- Node.js 18+（前端构建需要，仅宿主机构建时需要）
- Git（代码版本管理）

## 镜像分层结构

测试环境由三层镜像组成，从底层到上层：

```
┌─────────────────────────────────────────┐
│  应用镜像 (backend / frontend)          │  ← 每次代码变更重建
├─────────────────────────────────────────┤
│  基础镜像 (backend-base)                │  ← 依赖变更时才需重建
│  python:3.10-slim-bookworm              │
│  + 系统包 (pandoc, wkhtmltopdf, 字体)   │
│  + Python 包 (pyproject.toml)           │
│  + 编译工具 (gcc, cython)               │
└─────────────────────────────────────────┘
```

分层的好处：基础镜像变化少、体积大，只需构建一次；应用镜像变化频繁、构建快，每次代码更新只需重建应用层。

## 端口映射

三个版本的测试环境使用独立端口，可同时运行互不干扰：

| 版本 | MongoDB | Redis | Nginx(入口) | Docker 项目名 |
|------|---------|-------|-------------|--------------|
| 2.0  | 27017   | 6379  | 8080        | ta-v201      |
| 2.1  | 27018   | 6380  | 8081        | ta-v210      |
| 3.0  | 27019   | 6381  | 8082        | ta-v3        |

通过 Nginx 端口统一访问：前端页面和后端 API 都走同一个 Nginx 入口，`/api/` 路径自动代理到后端。

## 快速开始

### 一键构建并启动

```powershell
# 构建 v3.0 全套镜像并启动（首次使用）
.\docker\scripts\build-test-env.ps1 -Version 3.0
```

脚本会依次执行四个步骤：基础镜像 → 后端镜像 → 前端镜像 → 启动服务。

启动完成后访问 `http://localhost:8082` 即可使用。

### 只打包不启动

```powershell
.\docker\scripts\build-test-env.ps1 -Version 3.0 -SkipComposeUp
```

### 指定版本

```powershell
# v2.1 测试环境
.\docker\scripts\build-test-env.ps1 -Version 2.1

# 不指定 -Version 则自动读取项目根目录 VERSION 文件
.\docker\scripts\build-test-env.ps1
```

## 分步操作

实际开发中通常不需要每次都跑全部步骤。脚本支持 `-Step` 参数单独执行某一步：

### 只构建基础镜像

依赖变更（新增 Python 包、系统包）时才需要。脚本会自动检测是否已存在同名镜像，已存在则跳过。

```powershell
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step base

# 强制重建（即使已存在）
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step base -ForceRebuild
```

构建耗时约 5-10 分钟，主要时间花在安装系统包和 Python 依赖上。

### 只构建后端镜像

后端代码有改动时执行。镜像内会编译 Python 代码为 `.pyc` 字节码和 `.so`（Cython），保护源码。

```powershell
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step backend
```

构建耗时约 2-3 分钟。

### 只构建前端镜像

前端代码有改动时执行。脚本会先在宿主机运行 `npm run build`（或 `npx vite build`），然后将构建产物打包到 Nginx 镜像中。

```powershell
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step frontend

# 如果宿主机已有 dist 目录，跳过 npm build
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step frontend -SkipFrontendBuild
```

构建耗时约 1-2 分钟。

### 只启动服务

镜像都已构建好，只需要启动/重启服务时：

```powershell
.\docker\scripts\build-test-env.ps1 -Version 2.1.0 -Step compose

# 如果默认端口被占用，可临时改用其他端口
.\docker\scripts\build-test-env.ps1 -Version 2.1.0 -Step compose -MongoPort 27119 -RedisPort 6481 -NginxPort 8182
```

脚本会自动生成 `docker/docker-compose.dev-test.yml` 文件（版本感知的端口和镜像标签），然后通过 docker-compose 启动。

## 服务管理

启动后，使用以下命令管理测试环境（以 v3.0 为例）：

```powershell
# 查看容器状态
docker-compose -p ta-v3 -f docker/docker-compose.dev-test.yml ps

# 查看后端日志
docker-compose -p ta-v3 -f docker/docker-compose.dev-test.yml logs -f backend

# 查看前端日志
docker-compose -p ta-v3 -f docker/docker-compose.dev-test.yml logs -f frontend

# 重启某个服务（如后端代码更新后重新构建镜像）
docker-compose -p ta-v3 -f docker/docker-compose.dev-test.yml restart backend

# 停止所有服务
docker-compose -p ta-v3 -f docker/docker-compose.dev-test.yml down

# 停止并删除数据卷（重置数据库）
docker-compose -p ta-v3 -f docker/docker-compose.dev-test.yml down -v
```

### 容器说明

| 容器 | 作用 | 对应镜像 |
|------|------|---------|
| ta-v3-mongodb | MongoDB 数据库 | mongo:4.4 |
| ta-v3-redis | Redis 缓存 | redis:7-alpine |
| ta-v3-backend | FastAPI 后端 | tradingagents-pro-backend:3.0 |
| ta-v3-frontend | Vue 前端 (Nginx) | tradingagents-pro-frontend:3.0 |
| ta-v3-nginx | 反向代理 | nginx:alpine |

## 典型工作流

### 场景 1：首次搭建测试环境

```powershell
# 一键完成
.\docker\scripts\build-test-env.ps1 -Version 3.0
```

### 场景 2：后端代码改动后重新部署

```powershell
# 1. 重新构建后端镜像
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step backend

# 2. 重启后端容器
docker-compose -p ta-v3 -f docker/docker-compose.dev-test.yml up -d backend
```

### 场景 3：前端代码改动后重新部署

```powershell
# 1. 重新构建前端镜像（含 npm build）
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step frontend

# 2. 重启前端容器
docker-compose -p ta-v3 -f docker/docker-compose.dev-test.yml up -d frontend
```

### 场景 4：多版本并行测试

```powershell
# 同时启动 v2.1 和 v3.0 测试环境
.\docker\scripts\build-test-env.ps1 -Version 2.1
.\docker\scripts\build-test-env.ps1 -Version 3.0

# v2.1 访问 http://localhost:8081
# v3.0 访问 http://localhost:8082
```

### 场景 5：添加了新的 Python 依赖

```powershell
# 1. 重新构建基础镜像
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step base -ForceRebuild

# 2. 重新构建后端镜像（基于新的基础镜像）
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step backend

# 3. 重启
.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step compose
```

## 参数速查

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-Version` | 版本号 (2.0/2.1/3.0) | 读取 VERSION 文件 |
| `-Step` | 只执行某一步 (base/backend/frontend/compose) | 全部执行 |
| `-MongoPort` | 覆盖 MongoDB 宿主机端口 | 版本默认端口 |
| `-RedisPort` | 覆盖 Redis 宿主机端口 | 版本默认端口 |
| `-NginxPort` | 覆盖 Nginx 宿主机端口 | 版本默认端口 |
| `-SkipFrontendBuild` | 跳过宿主机 npm build，使用已有 dist | false |
| `-SkipComposeUp` | 只打包不启动服务 | false |
| `-SkipBase` | 跳过基础镜像构建 | false |
| `-SkipBackend` | 跳过后端镜像构建 | false |
| `-SkipFrontend` | 跳过前端镜像构建 | false |
| `-ForceRebuild` | 强制重建基础镜像 | false |
| `-Registry` | Docker Hub 用户名 | hsliup |

## 常见问题

### 基础镜像构建卡在下载 pandoc

Dockerfile 中使用了清华大学镜像源加速 apt 和 pip 下载，但个别包可能仍然较慢。可以尝试：

1. 确认 Docker Desktop 网络代理设置
2. 重试：`.\docker\scripts\build-test-env.ps1 -Version 3.0 -Step base -ForceRebuild`

### 前端 TypeScript 类型检查失败

脚本会自动回退到 `npx vite build`（跳过 `vue-tsc` 类型检查）。如果 vite build 也失败，检查 `frontend/` 目录下是否有语法错误。

### docker-compose stderr 红色输出

docker-compose 的进度信息输出到 stderr，PowerShell 会显示为红色，这不代表错误。只要最终显示 `构建完成!` 且容器状态正常即可。

### 启动时报 port is already allocated

测试环境会占用当前版本固定端口。例如 v2.1 使用 27018、6380、8081；如果本机已经运行了 [docker/docker-compose.dev-compiled.yml](docker/docker-compose.dev-compiled.yml) 里的开发环境容器，或者有其他容器已经占用了这些端口，测试环境会因为端口冲突启动失败。

可先查看当前占用：

```powershell
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

如果确认是开发环境占用了同版本端口，先停止它再重试：

```powershell
docker compose -f docker/docker-compose.dev-compiled.yml down
.\docker\scripts\build-test-env.ps1 -Version 2.1.0 -Step compose
```

如果是其他容器占用了端口，比如 8081 被 `tradingagents-mcp-memory` 占用，则需要先停止对应容器，或调整该容器自己的端口映射后再重试。

如果不想停现有服务，也可以直接覆盖测试环境端口，例如：

```powershell
.\docker\scripts\build-test-env.ps1 -Version 2.1.0 -Step compose -MongoPort 27118 -RedisPort 6480 -NginxPort 8181
```

### 容器启动后后端 health check 失败

后端首次启动需要初始化数据库（等待 MongoDB + 创建默认用户），约需 30-60 秒。可以查看日志确认：

```powershell
docker logs ta-v3-backend
```

默认登录账号：`admin` / `admin123`

### 数据持久化

MongoDB 和 Redis 数据存储在 Docker 命名卷中，`docker-compose down` 不会删除数据。如需重置：

```powershell
docker-compose -p ta-v3 -f docker/docker-compose.dev-test.yml down -v
```

### 迁移旧数据库

从旧环境（如 27017 端口的 MongoDB）迁移数据到新测试环境：

```powershell
# 1. 找到源 MongoDB 容器名
docker ps | grep mongo

# 2. 在两个容器间直接复制数据
docker exec <源容器名> mongodump --archive --username admin --password tradingagents123 --authenticationDatabase admin --db tradingagents | docker exec -i ta-v3-mongodb mongorestore --archive --username admin --password tradingagents123 --authenticationDatabase admin
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `docker/scripts/build-test-env.ps1` | 本文档对应的打包脚本 |
| `docker/Dockerfile.backend.base.ubuntu` | 基础镜像 Dockerfile |
| `docker/Dockerfile.backend.compiled.ubuntu` | 后端应用镜像 Dockerfile |
| `docker/Dockerfile.frontend` | 前端 Nginx 镜像 Dockerfile |
| `docker/nginx.conf` | 前端 Nginx SPA 配置 |
| `docker/nginx/nginx-proxy.conf` | 反向代理 Nginx 配置 |
| `docker/docker-compose.dev-test.yml` | 脚本自动生成的 compose 文件 |
| `docker/scripts/compile-and-cleanup.sh` | 容器内编译脚本 |
| `docker/scripts/docker-entrypoint.sh` | 容器入口脚本（自动初始化数据库） |
| `VERSION` | 版本号唯一来源 |
