# TradingAgents-CN 多架构镜像构建指南（Ubuntu 服务器）

> 📦 在 Ubuntu 22.04 Intel 服务器上构建支持 ARM 和 x86_64 的 Docker 镜像

## 🎯 目标

在 Ubuntu 22.04 Intel (x86_64) 服务器上构建多架构 Docker 镜像，支持：
- **linux/amd64** (Intel/AMD 处理器)
- **linux/arm64** (ARM 处理器：Apple Silicon、树莓派、AWS Graviton 等)

构建完成后自动推送到 Docker Hub，并清理本地镜像释放磁盘空间。

---

## 📋 前置准备

### 1. 系统要求

- **操作系统**: Ubuntu 22.04 LTS
- **架构**: x86_64 (Intel/AMD)
- **Docker**: 20.10+ (已安装)
- **磁盘空间**: 至少 10GB 可用空间（构建过程中需要）
- **网络**: 稳定的网络连接（需要下载依赖和推送镜像）

### 2. 安装 Docker Buildx

```bash
# 创建插件目录
mkdir -p ~/.docker/cli-plugins

# 下载 buildx（amd64 版本）
wget -O ~/.docker/cli-plugins/docker-buildx \
  https://github.com/docker/buildx/releases/download/v0.12.1/buildx-v0.12.1.linux-amd64

# 添加执行权限
chmod +x ~/.docker/cli-plugins/docker-buildx

# 验证安装
docker buildx version
```

### 3. 安装 QEMU（支持跨架构构建）

```bash
# 安装 QEMU 用户模式模拟器
sudo apt-get update
sudo apt-get install -y qemu-user-static binfmt-support

# 注册 QEMU 到 Docker Buildx
docker run --privileged --rm tonistiigi/binfmt --install all

# 验证支持的平台
docker buildx ls
```

您应该看到类似输出：
```
NAME/NODE       DRIVER/ENDPOINT STATUS  PLATFORMS
default *       docker
  default       default         running linux/amd64, linux/arm64, linux/arm/v7, ...
```

### 4. 创建 Buildx Builder

```bash
# 创建支持多架构的 builder
docker buildx create --name tradingagents-builder --use --platform linux/amd64,linux/arm64

# 启动 builder
docker buildx inspect --bootstrap

# 验证 builder 状态
docker buildx ls
```

您应该看到类似输出：
```
NAME/NODE                  DRIVER/ENDPOINT STATUS  PLATFORMS
tradingagents-builder *    docker-container
  tradingagents-builder0   unix:///var/run/docker.sock running linux/amd64*, linux/arm64*, ...
```

---

## 🚀 使用自动化脚本构建

### 步骤 1: 进入项目目录

```bash
cd /home/hsliup/TradingAgents-CN
```

### 步骤 2: 给脚本添加执行权限

```bash
chmod +x scripts/build-and-publish-linux.sh
```

### 步骤 3: 运行构建脚本

```bash
# 基本用法（默认构建 amd64 + arm64）
./scripts/build-and-publish-linux.sh your-dockerhub-username

# 指定版本
./scripts/build-and-publish-linux.sh your-dockerhub-username v1.0.0

# 指定版本和架构
./scripts/build-and-publish-linux.sh your-dockerhub-username v1.0.0 linux/amd64,linux/arm64
```

### 步骤 4: 输入 Docker Hub 密码

脚本会提示您输入 Docker Hub 密码：
```
步骤3: 登录Docker Hub...
Username: your-dockerhub-username
Password: [输入密码]
```

### 步骤 5: 等待构建完成

构建过程大约需要 **20-40 分钟**，具体取决于服务器性能和网络速度。

脚本会自动完成以下操作：
1. ✅ 检查环境（Docker、Buildx、Git）
2. ✅ 配置 Docker Buildx
3. ✅ 登录 Docker Hub
4. ✅ 构建后端镜像（amd64 + arm64）并推送
5. ✅ 构建前端镜像（amd64 + arm64）并推送
6. ✅ 验证镜像架构
7. ✅ 清理本地镜像和缓存

---

## 📊 构建过程详解

### 脚本执行流程

```
步骤1: 检查环境
  ✅ Docker已安装: Docker version 28.2.2
  ✅ Docker Buildx可用: github.com/docker/buildx v0.12.1
  ✅ Git已安装: git version 2.34.1
  ✅ 当前目录正确

步骤2: 配置Docker Buildx
  ✅ Builder 'tradingagents-builder' 已存在
  启动Builder...
  支持的平台: linux/amd64*, linux/arm64*, ...

步骤3: 登录Docker Hub
  ✅ 登录成功！

步骤4: 构建并推送后端镜像（多架构）
  镜像名称: your-dockerhub-username/tradingagents-backend
  目标架构: linux/amd64,linux/arm64
  开始时间: 2025-10-20 10:00:00
  
  构建并推送: your-dockerhub-username/tradingagents-backend:v1.0.0-preview
  [构建过程输出...]
  
  ✅ 后端镜像构建并推送成功！
  构建耗时: 1200秒 (20分钟)

步骤5: 构建并推送前端镜像（多架构）
  镜像名称: your-dockerhub-username/tradingagents-frontend
  目标架构: linux/amd64,linux/arm64
  开始时间: 2025-10-20 10:20:00
  
  构建并推送: your-dockerhub-username/tradingagents-frontend:v1.0.0-preview
  [构建过程输出...]
  
  ✅ 前端镜像构建并推送成功！
  构建耗时: 600秒 (10分钟)

步骤6: 验证镜像架构
  验证后端镜像: your-dockerhub-username/tradingagents-backend:v1.0.0-preview
  Platform:  linux/amd64
  Platform:  linux/arm64
  
  验证前端镜像: your-dockerhub-username/tradingagents-frontend:v1.0.0-preview
  Platform:  linux/amd64
  Platform:  linux/arm64

步骤7: 清理本地镜像和缓存
  清理本地镜像...
  清理悬空镜像...
  清理buildx缓存...
  ✅ 本地镜像和缓存已清理

========================================
🎉 Docker多架构镜像构建和发布完成！
========================================

已发布的镜像（支持 linux/amd64,linux/arm64）：
  后端: your-dockerhub-username/tradingagents-backend:v1.0.0-preview
  后端: your-dockerhub-username/tradingagents-backend:latest
  前端: your-dockerhub-username/tradingagents-frontend:v1.0.0-preview
  前端: your-dockerhub-username/tradingagents-frontend:latest

✅ 本地镜像已清理，服务器磁盘空间已释放
```

---

## 🔍 验证镜像

### 在服务器上验证

```bash
# 查看后端镜像支持的架构
docker buildx imagetools inspect your-dockerhub-username/tradingagents-backend:latest

# 查看前端镜像支持的架构
docker buildx imagetools inspect your-dockerhub-username/tradingagents-frontend:latest
```

输出示例：
```
Name:      your-dockerhub-username/tradingagents-backend:latest
MediaType: application/vnd.docker.distribution.manifest.list.v2+json
Digest:    sha256:abc123...

Manifests:
  Name:      your-dockerhub-username/tradingagents-backend:latest@sha256:def456...
  MediaType: application/vnd.docker.distribution.manifest.v2+json
  Platform:  linux/amd64
  
  Name:      your-dockerhub-username/tradingagents-backend:latest@sha256:ghi789...
  MediaType: application/vnd.docker.distribution.manifest.v2+json
  Platform:  linux/arm64
```

### 在 Docker Hub 上验证

1. 访问 https://hub.docker.com/repositories/your-dockerhub-username
2. 点击 `tradingagents-backend` 或 `tradingagents-frontend`
3. 点击 `Tags` 标签页
4. 查看 `OS/ARCH` 列，应该显示 `linux/amd64, linux/arm64`

---

## 💡 用户使用方法

### 在 x86_64 机器上使用

```bash
# Docker 会自动拉取 amd64 版本
docker pull your-dockerhub-username/tradingagents-backend:latest
docker pull your-dockerhub-username/tradingagents-frontend:latest
```

### 在 ARM 机器上使用

```bash
# Docker 会自动拉取 arm64 版本
docker pull your-dockerhub-username/tradingagents-backend:latest
docker pull your-dockerhub-username/tradingagents-frontend:latest
```

### 使用 Docker Compose

```bash
# 修改 docker-compose.hub.yml 中的镜像名称
# 然后启动
docker-compose -f docker-compose.hub.yml up -d
```

---

## ⚠️ 注意事项

### 1. 构建时间

- **后端镜像**: 15-25 分钟（ARM 部分较慢，因为通过 QEMU 模拟）
- **前端镜像**: 8-15 分钟
- **总计**: 约 25-40 分钟

### 2. 磁盘空间

- **构建过程中**: 需要约 5-8GB 临时空间
- **构建完成后**: 自动清理，释放磁盘空间
- **Docker Hub**: 镜像大小约 800MB（后端）+ 25MB（前端）

### 3. 网络要求

- 需要稳定的网络连接
- 推送镜像到 Docker Hub 需要上传约 1.5GB 数据（两个架构）
- 建议在网络状况良好时进行构建

### 4. 自动清理

脚本会在推送完成后自动清理：
- ✅ 本地构建的镜像
- ✅ 悬空镜像（dangling images）
- ✅ Buildx 构建缓存

这样可以释放服务器磁盘空间，避免占用过多资源。

---

## 🐛 常见问题

### 问题 1: `docker buildx` 命令不存在

**解决方案**: 按照"前置准备"部分安装 Docker Buildx

### 问题 2: 构建 ARM 镜像时速度很慢

**原因**: 在 x86_64 机器上通过 QEMU 模拟 ARM 架构，速度较慢

**解决方案**: 这是正常现象，耐心等待即可

### 问题 3: 推送镜像失败

**可能原因**:
- Docker Hub 登录失败
- 网络连接不稳定
- Docker Hub 用户名错误

**解决方案**:
```bash
# 手动登录测试
docker login -u your-dockerhub-username

# 检查网络连接
ping hub.docker.com
```

### 问题 4: 磁盘空间不足

**解决方案**:
```bash
# 清理 Docker 系统
docker system prune -a -f

# 清理 Buildx 缓存
docker buildx prune -a -f
```

---

## 📚 相关文档

- [Docker Buildx 官方文档](https://docs.docker.com/buildx/working-with-buildx/)
- [多架构镜像构建详细指南](./MULTIARCH_BUILD.md)
- [Docker 部署指南](./DOCKER_DEPLOYMENT_v1.0.0.md)

---

**最后更新**: 2025-01-20

