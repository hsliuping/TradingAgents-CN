# 🏗️ TradingAgents-CN Docker 镜像构建指南

本文档说明如何为不同架构构建 Docker 镜像。

---

## 📋 目录

- [快速开始](#快速开始)
- [架构选择](#架构选择)
- [构建脚本](#构建脚本)
- [使用方法](#使用方法)
- [性能对比](#性能对比)
- [常见问题](#常见问题)

---

## 🚀 快速开始

### 方案 1：使用预构建镜像（推荐）

```bash
# 从 Docker Hub 拉取（最快）
docker pull hsliuping/tradingagents-backend:v1.0.0-preview-amd64
docker pull hsliuping/tradingagents-frontend:v1.0.0-preview-amd64
```

### 方案 2：本地构建（按架构）

```bash
# AMD64 (Intel/AMD)
./scripts/build-amd64.sh

# ARM64 (ARM 服务器、树莓派、Apple Silicon)
./scripts/build-arm64.sh
```

### 方案 3：多架构构建（慢，不推荐）

```bash
# 同时构建 AMD64 + ARM64（非常慢）
./scripts/build-multiarch.sh
```

---

## 🎯 架构选择

### AMD64 (x86_64)

**适用设备**：
- ✅ Intel 处理器的 PC、笔记本
- ✅ AMD 处理器的 PC、服务器
- ✅ 大部分云服务器（AWS、阿里云、腾讯云等）
- ✅ Windows、Linux 服务器

**构建脚本**：
- Linux/macOS: `./scripts/build-amd64.sh`
- Windows: `.\scripts\build-amd64.ps1`

**构建时间**：约 5-10 分钟

---

### ARM64

**适用设备**：
- ✅ ARM 架构服务器（华为鲲鹏、飞腾等）
- ✅ 树莓派 4/5 (Raspberry Pi)
- ✅ NVIDIA Jetson 系列
- ✅ AWS Graviton 实例

**构建脚本**：
- Linux/macOS: `./scripts/build-arm64.sh`
- Windows: `.\scripts\build-arm64.ps1`

**构建时间**：
- ARM 设备上：约 10-20 分钟
- x86 交叉编译：约 20-40 分钟（慢）

---

### Apple Silicon (M1/M2/M3/M4)

**适用设备**：
- ✅ MacBook Pro/Air (M1/M2/M3/M4)
- ✅ Mac Mini (Apple Silicon)
- ✅ Mac Studio (M1/M2 Ultra)
- ✅ iMac (Apple Silicon)

**构建脚本**：
- macOS: `./scripts/build-arm64.sh`（与 ARM64 通用）

**构建时间**：约 5-8 分钟（原生架构，快）

**优势**：
- 🚀 原生性能，无需模拟
- ⚡ 构建速度比 x86 模拟快 3-5 倍
- 💚 运行效率高，功耗低
- 🔄 镜像与 ARM64 服务器完全通用

**说明**：
- Apple Silicon 使用 ARM64 架构，与 ARM 服务器镜像完全兼容
- 无需单独构建，直接使用 `build-arm64.sh` 即可

---

## 📦 构建脚本

### 1. AMD64 构建脚本

#### Linux/macOS

```bash
# 基本用法
./scripts/build-amd64.sh

# 推送到 Docker Hub
REGISTRY=your-dockerhub-username VERSION=v1.0.0 ./scripts/build-amd64.sh

# 自定义版本
VERSION=v1.0.1 ./scripts/build-amd64.sh
```

#### Windows (PowerShell)

```powershell
# 基本用法
.\scripts\build-amd64.ps1

# 推送到 Docker Hub
.\scripts\build-amd64.ps1 -Registry your-dockerhub-username -Version v1.0.0

# 自定义版本
.\scripts\build-amd64.ps1 -Version v1.0.1
```

---

### 2. ARM64 构建脚本

#### Linux/macOS

```bash
# 基本用法
./scripts/build-arm64.sh

# 推送到 Docker Hub
REGISTRY=your-dockerhub-username VERSION=v1.0.0 ./scripts/build-arm64.sh
```

#### Windows (PowerShell)

```powershell
# 基本用法
.\scripts\build-arm64.ps1

# 推送到 Docker Hub
.\scripts\build-arm64.ps1 -Registry your-dockerhub-username -Version v1.0.0
```

---

### 4. 多架构构建脚本（不推荐）

**⚠️ 警告**：同时构建多个架构非常慢（30-60 分钟），不推荐使用。

#### Linux/macOS

```bash
# 构建 AMD64 + ARM64（慢）
./scripts/build-multiarch.sh

# 推送到 Docker Hub
REGISTRY=your-dockerhub-username VERSION=v1.0.0 ./scripts/build-multiarch.sh
```

#### Windows (PowerShell)

```powershell
# 构建 AMD64 + ARM64（慢）
.\scripts\build-multiarch.ps1

# 推送到 Docker Hub
.\scripts\build-multiarch.ps1 -Registry your-dockerhub-username -Version v1.0.0
```

---

## 📊 性能对比

| 架构 | 设备示例 | 构建时间 | 运行性能 | 推荐度 |
|------|---------|---------|---------|--------|
| **AMD64** | Intel/AMD PC | 5-10 分钟 | ⭐⭐⭐⭐⭐ | ✅ 推荐 |
| **ARM64** | ARM 服务器 | 10-20 分钟 | ⭐⭐⭐⭐ | ✅ 推荐 |
| **Apple Silicon** | MacBook M1/M2 | 5-8 分钟 | ⭐⭐⭐⭐⭐ | ✅ 强烈推荐 |
| **多架构** | 任意设备 | 30-60 分钟 | - | ❌ 不推荐 |

---

## 🔧 使用方法

### 1. 本地构建后使用

```bash
# 1. 构建镜像
./scripts/build-amd64.sh

# 2. 查看镜像
docker images | grep tradingagents

# 3. 启动服务
docker-compose -f docker-compose.v1.0.0.yml up -d
```

### 2. 推送到 Docker Hub

```bash
# 1. 登录 Docker Hub
docker login

# 2. 构建并推送
REGISTRY=your-dockerhub-username ./scripts/build-amd64.sh

# 3. 在其他机器上拉取
docker pull your-dockerhub-username/tradingagents-backend:v1.0.0-preview-amd64
```

### 3. 使用预构建镜像

```bash
# 1. 拉取镜像
docker pull hsliuping/tradingagents-backend:v1.0.0-preview-amd64
docker pull hsliuping/tradingagents-frontend:v1.0.0-preview-amd64

# 2. 修改 docker-compose.yml 中的镜像名称
# image: hsliuping/tradingagents-backend:v1.0.0-preview-amd64

# 3. 启动服务
docker-compose up -d
```

---

## ❓ 常见问题

### Q1: 如何选择构建脚本？

**A**: 根据您的设备选择：

| 设备类型 | 推荐脚本 |
|---------|---------|
| Intel/AMD PC | `build-amd64.sh` |
| ARM 服务器 | `build-arm64.sh` |
| MacBook M1/M2/M3/M4 | `build-arm64.sh` |
| 树莓派 4/5 | `build-arm64.sh` |

### Q2: 为什么不推荐多架构构建？

**A**: 多架构构建的问题：
- ❌ 构建时间长（30-60 分钟）
- ❌ 占用大量 CPU 和内存
- ❌ 交叉编译可能出错
- ✅ 分架构构建更快（5-10 分钟）
- ✅ 更稳定可靠

### Q3: Apple Silicon 用户应该用哪个脚本？

**A**: 使用 `build-apple-silicon.sh`：
- ✅ 原生架构，构建快
- ✅ 性能最优
- ✅ 镜像与 ARM64 通用
- ✅ 可在 ARM 服务器上使用

### Q4: 构建失败怎么办？

**A**: 常见解决方法：

1. **检查 Docker 版本**
   ```bash
   docker --version  # 需要 19.03+
   docker buildx version  # 需要支持 buildx
   ```

2. **清理 Docker 缓存**
   ```bash
   docker system prune -a
   ```

3. **重新创建 builder**
   ```bash
   docker buildx rm tradingagents-builder-amd64
   ./scripts/build-amd64.sh
   ```

4. **检查网络连接**
   - 确保可以访问 Docker Hub
   - 确保可以访问 PyPI 镜像

### Q5: 如何加速构建？

**A**: 加速技巧：

1. **使用国内镜像**（已配置）
   - PyPI: 清华镜像
   - npm: 淘宝镜像

2. **使用 Docker 缓存**
   ```bash
   # 不清理缓存，利用已有层
   docker buildx build --cache-from=...
   ```

3. **使用预构建镜像**
   ```bash
   # 直接拉取，无需构建
   docker pull hsliuping/tradingagents-backend:v1.0.0-preview-amd64
   ```

### Q6: 镜像标签说明

| 标签 | 说明 | 示例 |
|------|------|------|
| `{version}` | 通用标签 | `v1.0.0-preview` |
| `{version}-amd64` | AMD64 专用 | `v1.0.0-preview-amd64` |
| `{version}-arm64` | ARM64 专用 | `v1.0.0-preview-arm64` |
| `{version}-apple-silicon` | Apple Silicon 专用 | `v1.0.0-preview-apple-silicon` |

### Q7: 如何验证镜像架构？

```bash
# 查看镜像详细信息
docker inspect tradingagents-backend:v1.0.0-preview | grep Architecture

# 或使用 buildx
docker buildx imagetools inspect tradingagents-backend:v1.0.0-preview
```

---

## 📚 相关文档

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Buildx 文档](https://docs.docker.com/buildx/working-with-buildx/)
- [多架构镜像指南](https://docs.docker.com/build/building/multi-platform/)

---

## 🆘 获取帮助

如果遇到问题：

1. 查看构建日志
2. 检查 Docker 版本和配置
3. 提交 Issue：[GitHub Issues](https://github.com/hsliuping/TradingAgents-CN/issues)

---

**最后更新**：2025-10-24

