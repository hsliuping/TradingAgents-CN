# 🐳 Docker 镜像仓库策略

## 📋 概述

为了提高发布效率，TradingAgents-CN 采用**分架构独立仓库**策略：

- **AMD64 版本**：独立仓库，频繁更新
- **ARM64 版本**：独立仓库，按需更新

---

## 🎯 为什么要分开？

### ❌ 旧方案：单一仓库 + 多架构

```
tradingagents-backend:v1.0.0
├── linux/amd64
└── linux/arm64
```

**问题**：
- ❌ 每次更新必须同时打包两个架构
- ❌ 构建时间长（30-60 分钟）
- ❌ AMD64 小更新也要等 ARM64 打包完成
- ❌ ARM64 用户少，但每次都要打包

### ✅ 新方案：独立仓库 + 单一架构

```
tradingagents-backend-amd64:v1.0.0  (只包含 AMD64)
tradingagents-backend-arm64:v1.0.0  (只包含 ARM64)
```

**优势**：
- ✅ 独立更新，互不影响
- ✅ AMD64 快速发布（5-10 分钟）
- ✅ ARM64 按需更新（节省时间）
- ✅ 用户根据架构选择对应仓库

---

## 📦 镜像仓库命名

### Docker Hub 仓库

| 架构 | 后端镜像 | 前端镜像 |
|------|---------|---------|
| **AMD64** | `hsliuping/tradingagents-backend-amd64` | `hsliuping/tradingagents-frontend-amd64` |
| **ARM64** | `hsliuping/tradingagents-backend-arm64` | `hsliuping/tradingagents-frontend-arm64` |

### 镜像标签

| 标签 | 说明 | 示例 |
|------|------|------|
| `latest` | 最新稳定版 | `hsliuping/tradingagents-backend-amd64:latest` |
| `v{version}` | 指定版本 | `hsliuping/tradingagents-backend-amd64:v1.0.0-preview` |
| `v{version}-rc{n}` | 候选版本 | `hsliuping/tradingagents-backend-amd64:v1.0.0-rc1` |
| `dev` | 开发版本 | `hsliuping/tradingagents-backend-amd64:dev` |

---

## 🚀 构建和发布流程

### 场景 1：AMD64 小更新（推荐）

```bash
# 1. 只构建 AMD64 版本（快速）
REGISTRY=hsliuping VERSION=v1.0.1 ./scripts/build-amd64.sh

# 2. 推送到 Docker Hub
# 自动推送到:
#   - hsliuping/tradingagents-backend-amd64:v1.0.1
#   - hsliuping/tradingagents-backend-amd64:latest
#   - hsliuping/tradingagents-frontend-amd64:v1.0.1
#   - hsliuping/tradingagents-frontend-amd64:latest

# 3. ARM64 用户继续使用旧版本（不受影响）
```

**时间**：5-10 分钟 ⚡

---

### 场景 2：ARM64 按需更新

```bash
# 1. 只在需要时构建 ARM64 版本
REGISTRY=hsliuping VERSION=v1.0.1 ./scripts/build-arm64.sh

# 2. 推送到 Docker Hub
# 自动推送到:
#   - hsliuping/tradingagents-backend-arm64:v1.0.1
#   - hsliuping/tradingagents-backend-arm64:latest
#   - hsliuping/tradingagents-frontend-arm64:v1.0.1
#   - hsliuping/tradingagents-frontend-arm64:latest
```

**时间**：10-20 分钟（ARM 设备）或 20-40 分钟（x86 交叉编译）

---

### 场景 3：重大版本发布（两个都更新）

```bash
# 1. 构建 AMD64 版本
REGISTRY=hsliuping VERSION=v2.0.0 ./scripts/build-amd64.sh

# 2. 构建 ARM64 版本
REGISTRY=hsliuping VERSION=v2.0.0 ./scripts/build-arm64.sh

# 3. 两个架构都更新到最新版本
```

**时间**：15-30 分钟（分开构建，可并行）

---

## 👥 用户使用指南

### AMD64 用户（Intel/AMD 处理器）

```bash
# 拉取镜像
docker pull hsliuping/tradingagents-backend-amd64:latest
docker pull hsliuping/tradingagents-frontend-amd64:latest

# 或指定版本
docker pull hsliuping/tradingagents-backend-amd64:v1.0.0-preview
```

**docker-compose.yml 配置**：

```yaml
services:
  backend:
    image: hsliuping/tradingagents-backend-amd64:latest
    # ...
  
  frontend:
    image: hsliuping/tradingagents-frontend-amd64:latest
    # ...
```

---

### ARM64 用户（ARM 服务器、树莓派）

```bash
# 拉取镜像
docker pull hsliuping/tradingagents-backend-arm64:latest
docker pull hsliuping/tradingagents-frontend-arm64:latest

# 或指定版本
docker pull hsliuping/tradingagents-backend-arm64:v1.0.0-preview
```

**docker-compose.yml 配置**：

```yaml
services:
  backend:
    image: hsliuping/tradingagents-backend-arm64:latest
    # ...
  
  frontend:
    image: hsliuping/tradingagents-frontend-arm64:latest
    # ...
```

---

### Apple Silicon 用户（M1/M2/M3/M4）

**重要说明**：Apple Silicon 使用 ARM64 架构，与 ARM 服务器镜像完全通用。

```bash
# 使用 ARM64 镜像（与 ARM 服务器相同）
docker pull hsliuping/tradingagents-backend-arm64:latest
docker pull hsliuping/tradingagents-frontend-arm64:latest
```

**docker-compose.yml 配置**：

```yaml
services:
  backend:
    image: hsliuping/tradingagents-backend-arm64:latest
    # ...

  frontend:
    image: hsliuping/tradingagents-frontend-arm64:latest
    # ...
```

**构建镜像**：

```bash
# Apple Silicon 用户使用 ARM64 构建脚本
REGISTRY=hsliuping VERSION=v1.0.0 ./scripts/build-arm64.sh
```

---

## 📊 版本管理策略

### AMD64 版本（主要用户群）

- **更新频率**：高频（每周或更频繁）
- **更新内容**：
  - ✅ Bug 修复
  - ✅ 功能优化
  - ✅ 性能改进
  - ✅ 安全更新

### ARM64 版本（小众用户群）

- **更新频率**：低频（每月或按需）
- **更新内容**：
  - ✅ 重大功能更新
  - ✅ 重要 Bug 修复
  - ✅ 安全更新
  - ⚠️ 小优化可延后

---

## 🔄 版本同步策略

### 策略 1：独立版本号（推荐）

AMD64 和 ARM64 可以有不同的版本号：

```
AMD64: v1.0.5  (最新)
ARM64: v1.0.3  (稳定版)
```

**优势**：
- ✅ 灵活性高
- ✅ AMD64 快速迭代
- ✅ ARM64 保持稳定

### 策略 2：同步版本号

重大版本保持同步：

```
AMD64: v2.0.0
ARM64: v2.0.0
```

**适用场景**：
- 重大版本发布
- API 变更
- 数据库结构变更

---

## 📝 发布检查清单

### AMD64 快速发布

- [ ] 代码提交并推送到 GitHub
- [ ] 运行 `./scripts/build-amd64.sh`
- [ ] 测试镜像是否正常运行
- [ ] 更新 CHANGELOG.md
- [ ] 通知 AMD64 用户更新

### ARM64 按需发布

- [ ] 确认需要更新 ARM64 版本
- [ ] 代码提交并推送到 GitHub
- [ ] 运行 `./scripts/build-arm64.sh`
- [ ] 测试镜像是否正常运行（在 ARM 设备上）
- [ ] 更新 CHANGELOG.md
- [ ] 通知 ARM64 用户更新

---

## 🎯 最佳实践

### 1. 优先更新 AMD64

```bash
# 大部分用户使用 AMD64，优先发布
REGISTRY=hsliuping VERSION=v1.0.1 ./scripts/build-amd64.sh
```

### 2. ARM64 批量更新

```bash
# 积累多个小更新后，一次性发布 ARM64
REGISTRY=hsliuping VERSION=v1.0.5 ./scripts/build-arm64.sh
```

### 3. 使用 CI/CD 自动化

```yaml
# GitHub Actions 示例
name: Build AMD64
on:
  push:
    branches: [main]
jobs:
  build-amd64:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build AMD64
        run: |
          REGISTRY=${{ secrets.DOCKER_USERNAME }} \
          VERSION=${{ github.ref_name }} \
          ./scripts/build-amd64.sh
```

### 4. 版本标签规范

```bash
# 开发版本
VERSION=dev ./scripts/build-amd64.sh

# 候选版本
VERSION=v1.0.0-rc1 ./scripts/build-amd64.sh

# 正式版本
VERSION=v1.0.0 ./scripts/build-amd64.sh
```

---

## 📚 相关文档

- [构建指南](./BUILD_GUIDE.md)
- [Docker 部署指南](./DOCKER_DEPLOYMENT.md)
- [版本发布流程](./RELEASE_PROCESS.md)

---

## 🆘 常见问题

### Q1: ARM64 用户如何知道有新版本？

**A**: 
- 查看 CHANGELOG.md
- 关注 GitHub Releases
- 订阅邮件通知

### Q2: 如果 ARM64 版本太旧怎么办？

**A**: 
- 提交 Issue 请求更新
- 或自行构建最新版本

### Q3: 能否自动同步两个架构？

**A**: 
- 可以，但会失去独立更新的优势
- 不推荐，除非是重大版本

### Q4: 如何验证镜像架构？

```bash
# 查看镜像架构
docker inspect hsliuping/tradingagents-backend-amd64:latest | grep Architecture

# 输出: "Architecture": "amd64"
```

---

**最后更新**：2025-10-24

