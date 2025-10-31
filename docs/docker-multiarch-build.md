# Docker 多架构构建指南

## 概述

TradingAgents-CN 现在支持多架构 Docker 镜像构建，可以在 AMD64 (x86_64) 和 ARM64 (ARM) 架构上运行。

## 架构支持

| 架构 | 说明 | 适用设备 |
|------|------|----------|
| `linux/amd64` | x86_64 架构 | 大多数服务器、PC、云服务器 |
| `linux/arm64` | ARM 64位架构 | ARM 服务器、树莓派 4/5、NVIDIA Jetson、Apple Silicon (M1/M2/M3) |

## 修改说明

### Dockerfile.backend

已修改为支持多架构：

```dockerfile
# 获取构建架构信息
ARG TARGETARCH

# 根据架构动态选择对应的包
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        PANDOC_ARCH="arm64"; \
        WKHTMLTOPDF_ARCH="arm64"; \
    else \
        PANDOC_ARCH="amd64"; \
        WKHTMLTOPDF_ARCH="amd64"; \
    fi && \
    # 下载对应架构的包
    wget -q https://github.com/jgm/pandoc/releases/download/3.8.2.1/pandoc-3.8.2.1-1-${PANDOC_ARCH}.deb && \
    ...
```

### Dockerfile.frontend

使用官方多架构基础镜像，无需修改：
- `node:22-alpine` - 原生支持多架构
- `nginx:alpine` - 原生支持多架构

## 构建方法

### 方法 1：使用构建脚本（推荐）

#### 本地构建（当前架构）

```bash
# 多架构脚本（自动检测当前架构）
./scripts/build-multiarch.sh

# 或专门构建 ARM64
./scripts/build-arm64.sh
```

#### 推送到 Docker Hub

```bash
# 推送多架构镜像
REGISTRY=your-dockerhub-username VERSION=v1.0.0 ./scripts/build-multiarch.sh

# 推送 ARM64 镜像
REGISTRY=your-dockerhub-username VERSION=v1.0.0 ./scripts/build-arm64.sh
```

### 方法 2：手动构建

#### 构建单一架构

```bash
# 构建 ARM64 后端
docker buildx build --platform linux/arm64 \
  -f Dockerfile.backend \
  -t tradingagents-backend:arm64 \
  --load .

# 构建 ARM64 前端
docker buildx build --platform linux/arm64 \
  -f Dockerfile.frontend \
  -t tradingagents-frontend:arm64 \
  --load .
```

#### 构建并推送多架构

```bash
# 创建 builder（首次需要）
docker buildx create --name multiarch-builder --use --platform linux/amd64,linux/arm64

# 构建并推送后端
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.backend \
  -t your-registry/tradingagents-backend:latest \
  --push .

# 构建并推送前端
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile.frontend \
  -t your-registry/tradingagents-frontend:latest \
  --push .
```

## 验证构建

### 查看镜像架构

```bash
# 查看本地镜像
docker images | grep tradingagents

# 查看远程镜像支持的架构
docker buildx imagetools inspect your-registry/tradingagents-backend:latest
```

### 测试运行

```bash
# 使用 docker-compose 启动
docker-compose -f docker-compose.v1.0.0.yml up -d

# 查看容器状态
docker-compose -f docker-compose.v1.0.0.yml ps

# 查看日志
docker-compose -f docker-compose.v1.0.0.yml logs -f backend
```

## 常见问题

### Q1: 为什么本地构建只能构建一个架构？

A: Docker 的 `--load` 选项只支持单一架构。如果需要构建多架构镜像，必须使用 `--push` 推送到远程仓库。

### Q2: 如何在 x86 机器上构建 ARM 镜像？

A: Docker Buildx 支持交叉编译（使用 QEMU 模拟）：

```bash
# 安装 QEMU（如果未安装）
docker run --privileged --rm tonistiigi/binfmt --install all

# 构建 ARM64 镜像
docker buildx build --platform linux/arm64 -f Dockerfile.backend -t tradingagents-backend:arm64 --load .
```

**注意**：交叉编译速度较慢，建议在目标架构上直接构建或使用 CI/CD 自动构建。

### Q3: ARM 构建失败怎么办？

A: 检查以下几点：

1. **确认 Docker Buildx 已安装**：
   ```bash
   docker buildx version
   ```

2. **确认 QEMU 已安装**（交叉编译需要）：
   ```bash
   docker run --privileged --rm tonistiigi/binfmt --install all
   ```

3. **查看详细错误日志**：
   ```bash
   docker buildx build --platform linux/arm64 -f Dockerfile.backend -t test --progress=plain .
   ```

4. **检查网络连接**：
   - Pandoc 和 wkhtmltopdf 需要从 GitHub 下载
   - 如果网络不稳定，可能需要配置代理或使用国内镜像

### Q4: 如何加速 ARM 构建？

A: 几种方法：

1. **使用预构建镜像**（推荐）：
   ```bash
   docker pull your-registry/tradingagents-backend:latest
   ```

2. **在 ARM 设备上直接构建**（避免 QEMU 模拟开销）

3. **使用 Docker 构建缓存**：
   ```bash
   docker buildx build --cache-from=type=registry,ref=your-registry/tradingagents-backend:buildcache \
                       --cache-to=type=registry,ref=your-registry/tradingagents-backend:buildcache \
                       ...
   ```

4. **使用 CI/CD 自动构建**（GitHub Actions、GitLab CI 等）

## 性能对比

| 架构 | 构建时间（估算） | 运行性能 |
|------|-----------------|---------|
| AMD64 (本地) | ~5-10 分钟 | 100% |
| ARM64 (本地) | ~10-20 分钟 | 80-90% |
| AMD64 → ARM64 (交叉编译) | ~30-60 分钟 | 80-90% |

**建议**：
- 开发环境：使用本地架构构建
- 生产环境：使用 CI/CD 自动构建多架构镜像并推送到仓库

## 相关文件

- `Dockerfile.backend` - 后端多架构 Dockerfile
- `Dockerfile.frontend` - 前端多架构 Dockerfile
- `scripts/build-multiarch.sh` - 多架构构建脚本
- `scripts/build-arm64.sh` - ARM64 专用构建脚本
- `docker-compose.v1.0.0.yml` - Docker Compose 配置

## 更新日志

- **2025-10-31**: 添加多架构支持，修改 Dockerfile.backend 使用 `TARGETARCH` 参数动态选择架构

