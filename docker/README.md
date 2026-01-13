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
2. **代码编译保护**：
   - 在**宿主机**上编译代码（使用 Cython）
   - Docker 镜像只包含编译后的 `.pyc` 和 `.so` 文件
   - Docker 镜像**不需要**安装编译工具，保持精简
3. **推送到 Docker Hub**：`hsliup/tradingagents-backend:latest`
4. **独立测试**：不影响现有的根目录 Docker 配置

## 📐 构建流程

```
宿主机（Ubuntu 22.04）                Docker 镜像
┌─────────────────────┐              ┌─────────────────────┐
│ 1. 安装编译工具      │              │                     │
│    - python3-dev    │              │  精简的 Python 镜像  │
│    - build-essential│              │  (无编译工具)        │
│    - cython         │              │                     │
├─────────────────────┤              ├─────────────────────┤
│ 2. 编译代码         │              │                     │
│    compile-code.sh  │              │                     │
│    ├─ app/ → .pyc   │              │                     │
│    ├─ core/ → .pyc  │              │                     │
│    └─ licensing/    │              │                     │
│       → .so (Cython)│              │                     │
├─────────────────────┤              ├─────────────────────┤
│ 3. 构建 Docker      │──────────────>│ 4. 复制编译产物      │
│    build-compile.sh │   COPY       │    - app/ (.pyc)    │
│                     │              │    - core/ (.pyc)   │
│                     │              │    - licensing/ (.so)│
└─────────────────────┘              └─────────────────────┘
```

## 🚀 快速开始

### 在 Ubuntu 22.04 服务器上构建和部署

**重要**: 代码编译在**宿主机**上进行，Docker 镜像只包含编译后的文件。

```bash
# ========================================
# 步骤 1: 准备宿主机环境
# ========================================
# 1.1 克隆代码
git clone https://github.com/your-repo/TradingAgentsCN.git
cd TradingAgentsCN

# 1.2 安装编译工具（宿主机需要，Docker 镜像不需要）
sudo apt-get update
sudo apt-get install -y python3-dev build-essential python3-pip
pip3 install cython

# 验证安装
python3 -c "import Cython; print('Cython 版本:', Cython.__version__)"
gcc --version

# ========================================
# 步骤 2: 编译代码（在宿主机上）
# ========================================
cd docker

# 2.1 运行编译脚本
./scripts/compile-code.sh

# 脚本会:
# - 复制源代码到 docker/build/compiled/
# - 编译 app/ 和 core/ 为 .pyc
# - 使用 Cython 编译 core/licensing/ 为 .so
# - 删除源码 .py 文件

# 2.2 验证编译结果
ls -la build/compiled/core/licensing/
# 应该看到 .so 文件，而不是 .py 文件

# ========================================
# 步骤 3: 配置环境变量
# ========================================
cp .env.docker ../.env
nano ../.env  # 配置 API 密钥

# ========================================
# 步骤 4: 构建并推送 Docker 镜像（前后端）
# ========================================
# 一键构建并推送前后端镜像
./scripts/build-and-push-all.sh

# 或者只构建后端镜像
./scripts/build-compile.sh --push

# ========================================
# 步骤 5: 启动服务
# ========================================
docker-compose -f docker-compose.compiled.yml up -d

# ========================================
# 步骤 6: 访问应用
# ========================================
# 前端: http://your-server:8082
# 后端 API: http://your-server:8082/api
```

### 使用已推送的 Docker Hub 镜像

```bash
# 1. 配置环境变量
cp docker/.env.docker .env
nano .env  # 配置 API 密钥

# 2. 拉取镜像
docker pull hsliup/tradingagents-pro-backend:latest
docker pull hsliup/tradingagents-pro-frontend:latest

# 3. 启动服务
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
  - `core/licensing/` - **Cython 编译为 `.so`**（最强保护）
  - `tradingagents/` - 保留源码（开源部分）
- **适用**: Ubuntu 22.04 服务器生产环境
- **构建参数**: `COMPILE_DIR=docker/build/compiled`

### Dockerfile.frontend
- **用途**: 前端镜像
- **特点**:
  - 构建阶段: Node.js 22 + Yarn 1.22.22
  - 运行阶段: Nginx Alpine
  - 支持 SPA 路由
  - 内部监听 80 端口（容器内部）
- **配置文件**: `nginx.conf`（前端静态文件服务）
- **适用**: 所有环境

## 📄 Nginx 配置文件说明

### nginx.conf
- **用途**: Frontend 容器内部的 Nginx 配置
- **功能**: 提供 Vue 3 静态文件服务
- **监听端口**: 80（容器内部）
- **特点**:
  - SPA 路由支持（try_files fallback）
  - 静态资源缓存策略
  - Gzip 压缩

### nginx-proxy.conf
- **用途**: Nginx 反向代理容器配置
- **功能**: 代理请求到 frontend 和 backend 容器
- **监听端口**: 8082（对外暴露）
- **代理规则**:
  - `/api/*` → `backend:8000`
  - `/*` → `frontend:80`
- **特点**:
  - 统一入口
  - 无跨域问题
  - 健康检查端点 `/health`

## 🔧 Docker Compose 配置说明

### docker-compose.compiled.yml（新版本 - 测试中）
- **用途**: 编译版生产配置
- **服务**: backend（编译版）, frontend, mongodb, redis, nginx
- **特点**:
  - 后端使用编译后的 `.pyc` 字节码
  - 在构建时自动编译代码
  - 支持从 Docker Hub 拉取或本地构建
  - Nginx 反向代理，统一入口（8082端口）
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
5. **自动检测并调用 Cython 编译 `core/licensing/`**

**使用方法**:
```bash
# 需要先安装 Cython 和编译工具
sudo apt-get install -y python3-dev build-essential
pip3 install cython

# 运行编译
./docker/scripts/compile-code.sh
```

**输出**: `docker/build/compiled/` 目录

---

### scripts/compile-licensing.sh
使用 Cython 编译 `core/licensing` 为 `.so` 共享库的脚本。

**功能**:
1. 检查 Cython 和编译工具
2. 为每个 `.py` 文件生成 Cython 扩展
3. 编译为 `.so` 共享库
4. 删除源码 `.py` 文件

**使用方法**:
```bash
# 单独运行（需要先运行 compile-code.sh）
./docker/scripts/compile-licensing.sh
```

**详细文档**: 参见 `CYTHON_COMPILATION_GUIDE.md`

---

### scripts/build-and-push-all.sh ⭐ 推荐（AMD64）
**一键构建并推送前后端镜像**（Pro 版本专用，AMD64 架构）

**功能**:
1. 编译 Python 代码为 .pyc 和 .so
2. 构建后端 Docker 镜像（编译版）
3. 构建前端 Docker 镜像
4. 推送所有镜像到 Docker Hub

**使用方法**:
```bash
# 完整构建并推送（推荐）
./docker/scripts/build-and-push-all.sh

# 只构建不推送
./docker/scripts/build-and-push-all.sh --skip-push

# 跳过代码编译（使用已有编译产物）
./docker/scripts/build-and-push-all.sh --skip-compile

# 只构建前端
./docker/scripts/build-and-push-all.sh --skip-backend

# 只构建后端
./docker/scripts/build-and-push-all.sh --skip-frontend

# 指定版本号和仓库
./docker/scripts/build-and-push-all.sh -r hsliup -t v1.0.0
```

**参数**:
- `-r, --registry REGISTRY`: Docker Hub 用户名（默认: hsliup）
- `-t, --tag TAG`: 镜像标签（默认: latest）
- `--skip-compile`: 跳过代码编译
- `--skip-backend`: 跳过后端镜像构建
- `--skip-frontend`: 跳过前端镜像构建
- `--skip-push`: 只构建不推送
- `-h, --help`: 显示帮助信息

**输出镜像**:
- 后端: `hsliup/tradingagents-pro-backend:latest`
- 前端: `hsliup/tradingagents-pro-frontend:latest`

---

### scripts/build-arm64.sh
**ARM64 架构镜像构建**

**功能**:
1. 使用 Docker Buildx 构建 ARM64 镜像
2. 支持跨平台构建（在 x86_64 上构建 ARM64）
3. 构建后端和前端 ARM64 镜像
4. 推送到 Docker Hub

**使用方法**:
```bash
# 完整构建并推送（ARM64）
./docker/scripts/build-arm64.sh

# 使用 QEMU 模拟器（跨平台构建）
./docker/scripts/build-arm64.sh --use-qemu

# 只构建前端
./docker/scripts/build-arm64.sh --skip-backend

# 指定版本号
./docker/scripts/build-arm64.sh -r hsliup -t v1.0.0
```

**参数**:
- `-r, --registry REGISTRY`: Docker Hub 用户名（默认: hsliup）
- `-t, --tag TAG`: 镜像标签（默认: latest）
- `--skip-compile`: 跳过代码编译
- `--skip-backend`: 跳过后端镜像构建
- `--skip-frontend`: 跳过前端镜像构建
- `--skip-push`: 只构建不推送
- `--use-qemu`: 使用 QEMU 模拟器（跨平台构建）

**输出镜像**:
- 后端: `hsliup/tradingagents-pro-backend:latest-arm64`
- 前端: `hsliup/tradingagents-pro-frontend:latest-arm64`

---

### scripts/build-multiarch.sh ⭐ 多架构（推荐）
**同时构建 AMD64 和 ARM64 镜像**

**功能**:
1. 使用 Docker Buildx 构建多架构镜像
2. 同时支持 AMD64 和 ARM64
3. **在目标架构上编译代码**（自动生成对应架构的 .so 文件）
4. 自动创建 manifest（Docker 自动选择架构）
5. 推送到 Docker Hub

**使用方法**:
```bash
# 完整构建并推送（多架构）
./docker/scripts/build-multiarch.sh

# 只构建前端
./docker/scripts/build-multiarch.sh --skip-backend

# 指定版本号
./docker/scripts/build-multiarch.sh -r hsliup -t v1.0.0
```

**参数**:
- `-r, --registry REGISTRY`: Docker Hub 用户名（默认: hsliup）
- `-t, --tag TAG`: 镜像标签（默认: latest）
- `--skip-backend`: 跳过后端镜像构建
- `--skip-frontend`: 跳过前端镜像构建
- `--skip-push`: 只构建不推送（注意：多架构构建会自动推送）

**输出镜像**:
- 后端: `hsliup/tradingagents-pro-backend:latest` (AMD64 + ARM64)
- 前端: `hsliup/tradingagents-pro-frontend:latest` (AMD64 + ARM64)

**优势**:
- ✅ 一次构建，多架构支持
- ✅ Docker 自动选择匹配的架构
- ✅ 自动在目标架构上编译（AMD64 生成 AMD64 的 .so，ARM64 生成 ARM64 的 .so）
- ✅ 简化部署流程
- ✅ 无需预编译，构建时自动编译和清理

**编译和清理**:
- `core/licensing/` → Cython 编译为 `.so`（最强保护）
- `core/` 其他模块 → 字节码编译为 `.pyc`
- `app/` → 字节码编译为 `.pyc`
- 自动删除源码，只保留必要的 `.py` 文件
- `tradingagents/` 保留源码（开源部分）

详见: [COMPILE_AND_CLEANUP_RULES.md](COMPILE_AND_CLEANUP_RULES.md)

---

### scripts/build-compile.sh
在 Ubuntu 22.04 服务器上构建编译版**后端**镜像的脚本。

**功能**:
1. 调用 `compile-code.sh` 编译代码
2. 构建后端 Docker 镜像
3. 可选推送到 Docker Hub

**使用方法**:
```bash
# 只构建后端镜像
./docker/scripts/build-compile.sh

# 构建并推送到 Docker Hub
./docker/scripts/build-compile.sh --push

# 指定版本号
./docker/scripts/build-compile.sh -t v1.0.0 --push
```

**参数**:
- `-p, --push`: 构建后推送到 Docker Hub
- `-t, --tag TAG`: 指定版本号（默认: latest）
- `-r, --registry REGISTRY`: 指定 Docker Hub 用户名（默认: hsliup）

**输出镜像**:
- 后端: `hsliup/tradingagents-pro-backend:latest`

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

复制 `.env.docker` 为 `../.env`（项目根目录）并配置以下关键变量：

```bash
# 复制环境变量文件
cp docker/.env.docker ../.env

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

