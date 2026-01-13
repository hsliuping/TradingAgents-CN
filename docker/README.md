# Docker 部署文件说明（新版本 - 测试中）

本目录包含 TradingAgents-CN Pro 的新版 Docker 部署配置，专门针对 Ubuntu 22.04 服务器上的编译版部署。

## 📁 目录结构

```
docker/
├── README.md                           # 本文件
├── Dockerfile.backend.compiled.ubuntu  # Ubuntu 服务器编译版 Dockerfile
├── Dockerfile.frontend                 # 前端 Dockerfile（复制自根目录）
├── .dockerignore                       # Docker 构建忽略文件
├── docker-compose.compiled.yml         # 编译版 Docker Compose 配置
├── .env.example                        # 环境变量示例
├── nginx/
│   └── nginx.conf                      # Nginx 反向代理配置（已存在）
├── scripts/
│   ├── build-compile.sh                # 编译版构建脚本（Ubuntu）
│   ├── compile-code.sh                 # 代码编译脚本
│   └── push-images.sh                  # 推送镜像脚本
└── build/                              # 临时构建目录（.gitignore）
    └── compiled/                       # 编译后的代码
```

## 🎯 设计目标

1. **在 Ubuntu 22.04 服务器上构建**：不依赖 Windows 便携版
2. **代码编译保护**：使用 `.pyc` 和 `.pyd` 文件
3. **推送到 Docker Hub**：`hsliup/tradingagents-backend:latest`
4. **独立测试**：不影响现有的根目录 Docker 配置

## 🚀 快速开始

### 在 Ubuntu 22.04 服务器上构建和部署

```bash
# 1. 克隆代码
git clone https://github.com/your-repo/TradingAgentsCN.git
cd TradingAgentsCN

# 2. 进入 docker 目录
cd docker

# 3. 复制环境变量文件
cp .env.example ../.env

# 4. 编辑 .env 文件，配置 API 密钥
nano ../.env

# 5. 构建编译版镜像
./scripts/build-compile.sh --push

# 6. 启动服务
docker-compose -f docker-compose.compiled.yml up -d

# 7. 访问应用
# 前端: http://your-server
# 后端 API: http://your-server/api
```

### 使用已推送的 Docker Hub 镜像

```bash
# 1. 拉取镜像
docker pull hsliup/tradingagents-backend:latest
docker pull hsliup/tradingagents-frontend:latest

# 2. 启动服务
docker-compose -f docker/docker-compose.compiled.yml up -d
```

## 📦 Dockerfile 说明

### Dockerfile.backend.compiled.ubuntu
- **用途**: Ubuntu 服务器编译版后端镜像（商业版）
- **特点**:
  - 在构建时编译 Python 代码为 `.pyc` 字节码
  - 不依赖 Windows 便携版的 `release/` 目录
  - 使用临时构建目录 `docker/build/compiled`
- **代码保护**:
  - `core/` 和 `app/` - 字节码编译为 `.pyc`
  - `core/licensing/` - 可选 Cython 编译为 `.pyd`
  - `tradingagents/` - 保留源码（开源部分）
- **适用**: Ubuntu 22.04 服务器生产环境
- **构建参数**: `COMPILE_DIR=docker/build/compiled`

### Dockerfile.frontend
- **用途**: 前端镜像
- **特点**:
  - 构建阶段: Node.js 22 + Yarn 1.22.22
  - 运行阶段: Nginx Alpine
  - 支持 SPA 路由
- **适用**: 所有环境

## 🔧 Docker Compose 配置说明

### docker-compose.compiled.yml（新版本 - 测试中）
- **用途**: 编译版生产配置
- **服务**: backend（编译版）, frontend, mongodb, redis, nginx
- **特点**:
  - 后端使用编译后的 `.pyc` 字节码
  - 在构建时自动编译代码
  - 支持从 Docker Hub 拉取或本地构建
  - Nginx 反向代理，统一入口（80端口）
  - 无跨域问题
- **适用**: Ubuntu 22.04 服务器生产环境
- **镜像**:
  - `hsliup/tradingagents-backend:latest`
  - `hsliup/tradingagents-frontend:latest`

---

**以下是根目录的旧版配置（保留用于兼容）**:

### ../docker-compose.yml
- **用途**: 基础配置
- **服务**: backend, frontend, mongodb, redis
- **端口**: 8000 (backend), 80 (frontend)

### ../docker-compose.hub.nginx.yml（推荐）
- **用途**: 生产环境配置
- **服务**: backend, frontend, mongodb, redis, nginx
- **特点**:
  - 使用 Nginx 反向代理
  - 前后端统一入口（80 端口）
  - 无跨域问题
  - 支持从 Docker Hub 拉取镜像
- **镜像**: `hsliup/tradingagents-backend:latest`, `hsliup/tradingagents-frontend:latest`

### ../docker-compose.hub.nginx.arm.yml
- **用途**: ARM64 架构（如树莓派、Apple Silicon）
- **镜像**: `hsliup/tradingagents-backend-arm64:latest`

## 🛠️ 构建脚本说明

### scripts/compile-code.sh
编译 Python 代码为字节码的脚本。

**功能**:
1. 复制源代码到 `docker/build/compiled`
2. 编译 `app/` 和 `core/` 为 `.pyc` 字节码
3. 删除源码 `.py` 文件（保留 `__init__.py`）
4. `tradingagents/` 保留源码（开源部分）
5. `core/licensing/` 可选 Cython 编译

**使用方法**:
```bash
./docker/scripts/compile-code.sh
```

**输出**: `docker/build/compiled/` 目录

---

### scripts/build-compile.sh
在 Ubuntu 22.04 服务器上构建编译版镜像的脚本。

**功能**:
1. 调用 `compile-code.sh` 编译代码
2. 构建 Docker 镜像
3. 可选推送到 Docker Hub

**使用方法**:
```bash
# 只构建镜像
./docker/scripts/build-compile.sh

# 构建并推送到 Docker Hub
./docker/scripts/build-compile.sh --push

# 指定版本号
./docker/scripts/build-compile.sh --version 1.0.0 --push
```

**参数**:
- `--push`: 构建后推送到 Docker Hub
- `--version VERSION`: 指定版本号（默认: latest）
- `--registry REGISTRY`: 指定 Docker Hub 用户名（默认: hsliup）

---

### scripts/push-images.sh
推送镜像到 Docker Hub 的脚本。

**使用方法**:
```bash
# 推送所有镜像
./docker/scripts/push-images.sh

# 只推送后端镜像
./docker/scripts/push-images.sh --backend-only

# 只推送前端镜像
./docker/scripts/push-images.sh --frontend-only

# 指定标签
./docker/scripts/push-images.sh --tag 1.0.0
```

**参数**:
- `-r, --registry REGISTRY`: Docker Hub 用户名（默认: hsliup）
- `-t, --tag TAG`: 镜像标签（默认: latest）
- `-b, --backend-only`: 只推送后端镜像
- `-f, --frontend-only`: 只推送前端镜像

## 📝 环境变量配置

复制 `.env.example` 为 `../.env`（项目根目录）并配置以下关键变量：

```bash
# 复制环境变量文件
cp docker/.env.example ../.env

# 编辑配置
nano ../.env
```

**关键配置**:

```bash
# LLM API 密钥
DASHSCOPE_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# 数据源 API 密钥
TUSHARE_TOKEN=your_token_here
FINNHUB_API_KEY=your_key_here

# 安全配置（生产环境必须修改）
JWT_SECRET=your_jwt_secret_here
CSRF_SECRET=your_csrf_secret_here
```

## 🔍 常见问题

### 1. 如何查看日志？
```bash
# 查看所有服务日志
docker-compose -f docker/docker-compose.compiled.yml logs -f

# 查看后端日志
docker-compose -f docker/docker-compose.compiled.yml logs -f backend

# 查看前端日志
docker-compose -f docker/docker-compose.compiled.yml logs -f frontend
```

### 2. 如何重启服务？
```bash
docker-compose -f docker/docker-compose.compiled.yml restart
```

### 3. 如何停止服务？
```bash
docker-compose -f docker/docker-compose.compiled.yml down
```

### 4. 如何清理构建缓存？
```bash
# 清理编译目录
rm -rf docker/build/compiled

# 清理 Docker 构建缓存
docker builder prune -a
```

### 5. 如何更新镜像？
```bash
# 拉取最新镜像
docker pull hsliup/tradingagents-backend:latest
docker pull hsliup/tradingagents-frontend:latest

# 重启服务
docker-compose -f docker/docker-compose.compiled.yml up -d
```

### 4. 如何清理数据？
```bash
# 停止并删除容器、网络、数据卷
docker-compose -f docker/docker-compose.hub.nginx.yml down -v
```

## 📚 相关文档

- [Docker 部署指南](../docs/deployment/docker/DOCKER_DEPLOYMENT_v1.0.0.md)
- [Docker 文件说明](../docs/deployment/docker/DOCKER_FILES_README.md)
- [编译版打包说明](../scripts/deployment/README_PRO_PACKAGING.md)

---

**最后更新**: 2026-01-13  
**版本**: v1.0.0

