# GitHub Actions 自动构建多架构 Docker 镜像

本指南将帮助您设置 GitHub Actions 自动构建和发布多架构（amd64 + arm64）Docker 镜像到 Docker Hub。

---

## 📋 前置准备

### 1. Docker Hub 账号

如果还没有 Docker Hub 账号，请先注册：
- 访问 https://hub.docker.com
- 点击 "Sign Up" 注册账号
- 记住您的用户名（后续需要用到）

### 2. 创建 Docker Hub Access Token

为了让 GitHub Actions 能够推送镜像到 Docker Hub，需要创建一个访问令牌：

1. 登录 Docker Hub
2. 点击右上角头像 → **Account Settings**
3. 左侧菜单选择 **Security**
4. 点击 **New Access Token**
5. 填写信息：
   - **Access Token Description**: `GitHub Actions - TradingAgents-CN`
   - **Access permissions**: 选择 **Read, Write, Delete**
6. 点击 **Generate**
7. **重要**：复制生成的 token（只显示一次，请妥善保存）

---

## 🔐 配置 GitHub Secrets

### 1. 打开仓库设置

1. 访问您的 GitHub 仓库：`https://github.com/YOUR_USERNAME/TradingAgents-CN`
2. 点击 **Settings** 标签
3. 左侧菜单选择 **Secrets and variables** → **Actions**

### 2. 添加 Secrets

点击 **New repository secret**，添加以下两个 secrets：

#### Secret 1: DOCKERHUB_USERNAME

- **Name**: `DOCKERHUB_USERNAME`
- **Value**: 您的 Docker Hub 用户名（例如：`zhangsan`）
- 点击 **Add secret**

#### Secret 2: DOCKERHUB_TOKEN

- **Name**: `DOCKERHUB_TOKEN`
- **Value**: 刚才复制的 Docker Hub Access Token
- 点击 **Add secret**

### 3. 验证配置

确保您看到两个 secrets：
- ✅ `DOCKERHUB_USERNAME`
- ✅ `DOCKERHUB_TOKEN`

---

## 🚀 触发自动构建

GitHub Actions workflow 已经配置好（`.github/workflows/docker-publish.yml`），支持两种触发方式：

### 方式 1: 推送 Git Tag（推荐）

当您推送一个以 `v` 开头的 tag 时，会自动触发构建：

```bash
# 1. 提交所有更改
git add .
git commit -m "feat: 准备发布 v1.0.1"

# 2. 创建并推送 tag
git tag v1.0.1
git push origin v1.0.1

# 或者一次性推送代码和 tag
git push origin v1.0.0-preview --tags
```

**生成的镜像标签**：
- `your-username/tradingagents-backend:v1.0.1`
- `your-username/tradingagents-backend:latest`
- `your-username/tradingagents-backend:1.0`
- `your-username/tradingagents-frontend:v1.0.1`
- `your-username/tradingagents-frontend:latest`
- `your-username/tradingagents-frontend:1.0`

### 方式 2: 手动触发

1. 访问 GitHub 仓库
2. 点击 **Actions** 标签
3. 左侧选择 **Docker Publish to Docker Hub**
4. 点击右侧 **Run workflow** 按钮
5. 选择分支（例如 `v1.0.0-preview`）
6. 点击 **Run workflow**

**生成的镜像标签**：
- `your-username/tradingagents-backend:latest`
- `your-username/tradingagents-frontend:latest`

---

## 📊 监控构建进度

### 1. 查看 Workflow 运行状态

1. 访问 GitHub 仓库
2. 点击 **Actions** 标签
3. 查看最新的 workflow 运行记录

### 2. 查看详细日志

点击具体的 workflow 运行记录，可以看到：
- ✅ Checkout repository
- ✅ Set up QEMU（支持多架构）
- ✅ Set up Docker Buildx
- ✅ Log in to Docker Hub
- ✅ Extract metadata for backend
- ✅ Build and push backend image（**这一步最耗时**）
- ✅ Extract metadata for frontend
- ✅ Build and push frontend image
- ✅ Summary

### 3. 预计构建时间

| 步骤 | 预计时间 | 说明 |
|------|---------|------|
| 环境准备 | 1-2 分钟 | Checkout、QEMU、Buildx |
| 后端构建 | 15-30 分钟 | 包含 amd64 和 arm64 |
| 前端构建 | 8-15 分钟 | 包含 amd64 和 arm64 |
| **总计** | **25-50 分钟** | 取决于缓存命中率 |

**注意**：
- 首次构建会比较慢（30-50 分钟）
- 后续构建会利用 GitHub Actions 缓存，速度更快（15-25 分钟）
- ARM 架构构建通过 QEMU 模拟，比 amd64 慢 3-5 倍

---

## ✅ 验证构建结果

### 1. 查看 GitHub Actions Summary

构建完成后，在 workflow 运行页面会显示摘要：

```
## Docker Images Published 🚀

### Multi-Architecture Support
✅ linux/amd64 (Intel/AMD x86_64)
✅ linux/arm64 (Apple Silicon, Raspberry Pi, AWS Graviton)

### Backend Image
your-username/tradingagents-backend:v1.0.1
your-username/tradingagents-backend:latest

### Frontend Image
your-username/tradingagents-frontend:v1.0.1
your-username/tradingagents-frontend:latest
```

### 2. 在 Docker Hub 上验证

1. 访问 https://hub.docker.com
2. 登录您的账号
3. 查看仓库：
   - `your-username/tradingagents-backend`
   - `your-username/tradingagents-frontend`
4. 点击 **Tags** 标签，查看镜像版本
5. 点击具体的 tag，查看支持的架构：
   - ✅ `linux/amd64`
   - ✅ `linux/arm64`

### 3. 本地验证

```bash
# 验证后端镜像支持的架构
docker buildx imagetools inspect your-username/tradingagents-backend:latest

# 验证前端镜像支持的架构
docker buildx imagetools inspect your-username/tradingagents-frontend:latest
```

**预期输出**：
```
Name:      your-username/tradingagents-backend:latest
MediaType: application/vnd.docker.distribution.manifest.list.v2+json
Digest:    sha256:...

Manifests:
  Name:      your-username/tradingagents-backend:latest@sha256:...
  MediaType: application/vnd.docker.distribution.manifest.v2+json
  Platform:  linux/amd64
  
  Name:      your-username/tradingagents-backend:latest@sha256:...
  MediaType: application/vnd.docker.distribution.manifest.v2+json
  Platform:  linux/arm64
```

---

## 🎯 使用自动构建的镜像

### 在任何平台上使用

```bash
# Docker 会自动选择匹配当前平台的镜像
docker pull your-username/tradingagents-backend:latest
docker pull your-username/tradingagents-frontend:latest

# 运行容器
docker run -d -p 8000:8000 your-username/tradingagents-backend:latest
```

### 使用 docker-compose

修改 `docker-compose.hub.yml` 中的镜像名称：

```yaml
services:
  backend:
    image: your-username/tradingagents-backend:latest
    # ...
  
  frontend:
    image: your-username/tradingagents-frontend:latest
    # ...
```

然后运行：

```bash
docker-compose -f docker-compose.hub.yml up -d
```

---

## 🔧 高级配置

### 1. 修改触发条件

编辑 `.github/workflows/docker-publish.yml`：

```yaml
on:
  push:
    tags:
      - 'v*'           # 推送 v* tag 时触发
    branches:
      - main           # 推送到 main 分支时触发
      - v1.0.0-preview # 推送到特定分支时触发
  workflow_dispatch:   # 允许手动触发
```

### 2. 只构建单个架构（加速测试）

如果只想构建 amd64 架构（用于快速测试）：

```yaml
- name: Build and push backend image
  uses: docker/build-push-action@v5
  with:
    platforms: linux/amd64  # 只构建 amd64
    # ...
```

### 3. 添加构建通知

可以添加 Slack、Discord、Email 等通知：

```yaml
- name: Notify on success
  if: success()
  run: |
    curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"Docker images built successfully!"}' \
      ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

## 🐛 常见问题

### Q1: 构建失败：unauthorized: authentication required

**原因**：Docker Hub 认证失败

**解决方案**：
1. 检查 GitHub Secrets 中的 `DOCKERHUB_USERNAME` 和 `DOCKERHUB_TOKEN` 是否正确
2. 确认 Docker Hub Access Token 没有过期
3. 重新生成 Access Token 并更新 Secret

### Q2: 构建超时或非常慢

**原因**：ARM 架构构建通过 QEMU 模拟，速度较慢

**解决方案**：
1. 等待构建完成（首次构建可能需要 30-50 分钟）
2. 后续构建会利用缓存，速度更快
3. 如果只需要 amd64，可以修改 `platforms: linux/amd64`

### Q3: 构建失败：no space left on device

**原因**：GitHub Actions runner 磁盘空间不足

**解决方案**：
在构建前添加清理步骤：

```yaml
- name: Free disk space
  run: |
    docker system prune -af
    docker volume prune -f
```

### Q4: 如何查看构建日志？

1. 访问 GitHub 仓库 → **Actions** 标签
2. 点击具体的 workflow 运行记录
3. 点击 **Build and push backend image** 或 **Build and push frontend image**
4. 展开查看详细日志

### Q5: 如何取消正在运行的构建？

1. 访问 GitHub 仓库 → **Actions** 标签
2. 点击正在运行的 workflow
3. 点击右上角 **Cancel workflow**

---

## 📈 优化建议

### 1. 使用缓存加速构建

GitHub Actions 已经配置了缓存：

```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

这会缓存 Docker 层，加速后续构建。

### 2. 定期清理旧镜像

在 Docker Hub 上设置自动清理策略：
1. 访问仓库设置
2. 选择 **Manage tags**
3. 设置保留策略（例如：保留最近 10 个 tag）

### 3. 使用 Matrix 并行构建

如果想要更快的构建速度，可以并行构建不同架构：

```yaml
strategy:
  matrix:
    platform: [linux/amd64, linux/arm64]
```

但这会消耗更多的 GitHub Actions 配额。

---

## 📚 相关文档

- [Docker 多架构构建通用指南](./MULTIARCH_BUILD.md)
- [Docker 多架构构建性能优化](./MULTIARCH_BUILD_OPTIMIZATION.md)
- [GitHub Actions 官方文档](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)

---

## 🎉 总结

通过 GitHub Actions 自动构建，您可以：

✅ **自动化发布**：推送 tag 即可自动构建和发布镜像  
✅ **多架构支持**：一次构建，支持 amd64 和 arm64  
✅ **缓存加速**：利用 GitHub Actions 缓存，加速后续构建  
✅ **版本管理**：自动生成多个版本标签（latest、v1.0.0、1.0 等）  
✅ **无需本地构建**：不占用本地服务器资源和磁盘空间  
✅ **免费使用**：GitHub Actions 对公开仓库免费（每月 2000 分钟）

现在，您只需要专注于开发代码，推送 tag 后，GitHub Actions 会自动帮您构建和发布 Docker 镜像！🚀

