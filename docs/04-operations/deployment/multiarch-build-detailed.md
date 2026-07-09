# TradingAgents-CN 多架构 Docker 镜像构建指南

> 🏗️ 支持在 ARM 和 x86_64 架构上运行 TradingAgents-CN

## 📋 概述

TradingAgents-CN 支持构建多架构 Docker 镜像，可以在以下平台上运行：

- **amd64 (x86_64)**: Intel/AMD 处理器（常见的服务器和 PC）
- **arm64 (aarch64)**: ARM 处理器（Apple Silicon M1/M2/M3、树莓派 4/5、AWS Graviton 等）

## 🎯 为什么需要多架构镜像？

### 问题

默认情况下，Docker 镜像只为构建时的平台架构编译。如果在 x86_64 机器上构建镜像，然后在 ARM 机器上运行，会出现以下错误：

```
exec /usr/local/bin/python: exec format error
```

或

```
WARNING: The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)
```

### 解决方案

使用 **Docker Buildx** 构建多架构镜像，一次构建，多平台运行。

---

## 🛠️ 前置要求

### 1. Docker 版本

- **Docker 19.03+** (推荐 20.10+)
- **Docker Buildx** 插件（Docker Desktop 自带）

检查版本：

```bash
docker --version
docker buildx version
```

### 2. 启用 QEMU（跨平台构建）

如果需要在 x86_64 机器上构建 ARM 镜像（或反之），需要安装 QEMU：

```bash
# Linux
docker run --privileged --rm tonistiigi/binfmt --install all

# macOS/Windows (Docker Desktop 自动支持)
# 无需额外配置
```

验证支持的平台：

```bash
docker buildx ls
```

应该看到类似输出：

```
NAME/NODE       DRIVER/ENDPOINT STATUS  PLATFORMS
default *       docker
  default       default         running linux/amd64, linux/arm64, linux/arm/v7, ...
```

---

## 🚀 快速开始

### 方法 1: 使用自动化脚本（推荐）

我们提供了自动化构建脚本，支持 Linux/macOS 和 Windows。

#### Linux/macOS

```bash
# 本地构建（当前架构）
./scripts/build-multiarch.sh

# 构建并推送到 Docker Hub
REGISTRY=your-dockerhub-username VERSION=v1.0.0 ./scripts/build-multiarch.sh
```

#### Windows (PowerShell)

```powershell
# 本地构建（当前架构）
.\scripts\build-multiarch.ps1

# 构建并推送到 Docker Hub
.\scripts\build-multiarch.ps1 -Registry your-dockerhub-username -Version v1.0.0
```

### 方法 2: 手动构建

#### 步骤 1: 创建 Buildx Builder

```bash
# 创建新的 builder（支持多架构）
docker buildx create --name tradingagents-builder --use --platform linux/amd64,linux/arm64

# 启动 builder
docker buildx inspect --bootstrap
```

#### 步骤 2: 构建后端镜像

```bash
# 构建并推送到 Docker Hub（多架构）
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f Dockerfile.backend \
  -t your-dockerhub-username/tradingagents-backend:v1.0.0 \
  --push \
  .

# 或者只构建本地镜像（单一架构）
docker buildx build \
  --platform linux/amd64 \
  -f Dockerfile.backend \
  -t tradingagents-backend:v1.0.0 \
  --load \
  .
```

#### 步骤 3: 构建前端镜像

```bash
# 构建并推送到 Docker Hub（多架构）
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f Dockerfile.frontend \
  -t your-dockerhub-username/tradingagents-frontend:v1.0.0 \
  --push \
  .

# 或者只构建本地镜像（单一架构）
docker buildx build \
  --platform linux/amd64 \
  -f Dockerfile.frontend \
  -t tradingagents-frontend:v1.0.0 \
  --load \
  .
```

---

## 📦 使用多架构镜像

### 从 Docker Hub 拉取

如果镜像已推送到 Docker Hub，可以直接拉取：

```bash
# Docker 会自动选择匹配当前平台的镜像
docker pull your-dockerhub-username/tradingagents-backend:v1.0.0
docker pull your-dockerhub-username/tradingagents-frontend:v1.0.0
```

### 使用 Docker Compose

修改 `docker-compose.v1.0.0.yml`，使用远程镜像：

```yaml
services:
  backend:
    image: your-dockerhub-username/tradingagents-backend:v1.0.0
    # 注释掉 build 部分
    # build:
    #   context: .
    #   dockerfile: Dockerfile.backend
    ...

  frontend:
    image: your-dockerhub-username/tradingagents-frontend:v1.0.0
    # 注释掉 build 部分
    # build:
    #   context: .
    #   dockerfile: Dockerfile.frontend
    ...
```

然后启动：

```bash
docker-compose -f docker-compose.v1.0.0.yml up -d
```

---

## 🔍 验证镜像架构

### 查看镜像支持的架构

```bash
docker buildx imagetools inspect your-dockerhub-username/tradingagents-backend:v1.0.0
```

输出示例：

```
Name:      your-dockerhub-username/tradingagents-backend:v1.0.0
MediaType: application/vnd.docker.distribution.manifest.list.v2+json
Digest:    sha256:abc123...

Manifests:
  Name:      your-dockerhub-username/tradingagents-backend:v1.0.0@sha256:def456...
  MediaType: application/vnd.docker.distribution.manifest.v2+json
  Platform:  linux/amd64

  Name:      your-dockerhub-username/tradingagents-backend:v1.0.0@sha256:ghi789...
  MediaType: application/vnd.docker.distribution.manifest.v2+json
  Platform:  linux/arm64
```

### 查看本地镜像架构

```bash
docker inspect tradingagents-backend:v1.0.0 | grep Architecture
```

---

## 🐛 常见问题

### 问题 1: `--load` 不支持多架构

**错误信息**:
```
ERROR: docker exporter does not currently support exporting manifest lists
```

**原因**: `--load` 只能加载单一架构的镜像到本地 Docker。

**解决方案**:
- 使用 `--push` 推送到远程仓库（支持多架构）
- 或者只构建当前平台的镜像：
  ```bash
  docker buildx build --platform linux/amd64 --load ...
  ```

### 问题 2: ARM 镜像构建速度慢

**原因**: 在 x86_64 机器上通过 QEMU 模拟 ARM 架构，速度较慢。

**解决方案**:
- 使用 ARM 原生机器构建（如 Apple Silicon Mac、AWS Graviton）
- 或者使用 CI/CD 服务（GitHub Actions、GitLab CI）的多架构 runner

### 问题 3: Python 包在 ARM 上安装失败

**错误信息**:
```
ERROR: Could not find a version that satisfies the requirement xxx
```

**原因**: 某些 Python 包没有提供 ARM 预编译的 wheel。

**解决方案**:
- 在 Dockerfile 中安装编译工具：
  ```dockerfile
  RUN apt-get update && apt-get install -y gcc g++ make
  ```
- 或者使用支持 ARM 的替代包

### 问题 4: MongoDB/Redis 镜像不支持 ARM

**解决方案**:
- **MongoDB**: 使用 `mongo:4.4` 或更高版本（官方支持 ARM）
- **Redis**: 使用 `redis:7-alpine`（官方支持 ARM）

---

## 📊 性能对比

| 平台 | 架构 | 构建时间（后端） | 构建时间（前端） | 运行性能 |
|------|------|-----------------|-----------------|---------|
| Intel/AMD | amd64 | ~5 分钟 | ~3 分钟 | 100% |
| Apple M1/M2 | arm64 | ~4 分钟 | ~2 分钟 | 110-120% |
| 树莓派 4 | arm64 | ~15 分钟 | ~8 分钟 | 30-40% |
| AWS Graviton | arm64 | ~5 分钟 | ~3 分钟 | 100-110% |

> 注意: 性能数据仅供参考，实际性能取决于具体硬件配置。

---

## 🎓 最佳实践

### 1. 使用 CI/CD 自动构建

在 GitHub Actions 中自动构建多架构镜像：

```yaml
name: Build Multi-Arch Docker Images

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up QEMU
        uses: docker/setup-qemu-action@v2
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Login to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          file: ./Dockerfile.backend
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ secrets.DOCKERHUB_USERNAME }}/tradingagents-backend:${{ github.ref_name }}
```

### 2. 使用缓存加速构建

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --cache-from type=registry,ref=your-dockerhub-username/tradingagents-backend:buildcache \
  --cache-to type=registry,ref=your-dockerhub-username/tradingagents-backend:buildcache,mode=max \
  -t your-dockerhub-username/tradingagents-backend:v1.0.0 \
  --push \
  .
```

### 3. 分阶段构建优化

Dockerfile 已经使用了多阶段构建（前端），可以进一步优化：

```dockerfile
# 使用更小的基础镜像
FROM python:3.10-slim AS base

# 构建阶段
FROM base AS builder
RUN pip install --user ...

# 运行阶段
FROM base AS runtime
COPY --from=builder /root/.local /root/.local
```

---

## 📚 参考资料

- [Docker Buildx 官方文档](https://docs.docker.com/buildx/working-with-buildx/)
- [多架构镜像最佳实践](https://docs.docker.com/build/building/multi-platform/)
- [QEMU 用户模式](https://www.qemu.org/docs/master/user/main.html)

---

## 🆘 获取帮助

如果遇到问题，请：

1. 查看本文档的"常见问题"部分
2. 在 GitHub Issues 中搜索类似问题
3. 提交新的 Issue，并附上：
   - 操作系统和架构信息
   - Docker 版本
   - 完整的错误日志
   - 构建命令

---

**最后更新**: 2025-01-20

