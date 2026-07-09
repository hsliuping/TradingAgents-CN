# GitHub Actions 自动构建 - 快速开始

5 分钟设置 GitHub Actions 自动构建多架构 Docker 镜像。

---

## 🚀 快速设置（5 步）

### 步骤 1: 创建 Docker Hub Access Token

1. 登录 https://hub.docker.com
2. 点击右上角头像 → **Account Settings** → **Security**
3. 点击 **New Access Token**
4. 填写描述：`GitHub Actions - TradingAgents-CN`
5. 权限选择：**Read, Write, Delete**
6. 点击 **Generate** 并**复制 token**（只显示一次）

### 步骤 2: 配置 GitHub Secrets

1. 访问您的 GitHub 仓库
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**，添加两个 secrets：

| Name | Value |
|------|-------|
| `DOCKERHUB_USERNAME` | 您的 Docker Hub 用户名 |
| `DOCKERHUB_TOKEN` | 刚才复制的 Access Token |

### 步骤 3: 推送代码到 GitHub

```bash
# 提交所有更改
git add .
git commit -m "feat: 配置 GitHub Actions 自动构建"
git push origin v1.0.0-preview
```

### 步骤 4: 创建并推送 Tag

```bash
# 创建 tag
git tag v1.0.1

# 推送 tag（会自动触发构建）
git push origin v1.0.1
```

### 步骤 5: 查看构建进度

1. 访问 GitHub 仓库 → **Actions** 标签
2. 查看 **Docker Publish to Docker Hub** workflow
3. 等待构建完成（约 25-50 分钟）

---

## ✅ 验证结果

### 在 Docker Hub 上查看

访问 https://hub.docker.com/r/your-username/tradingagents-backend

应该看到：
- ✅ `v1.0.1` tag
- ✅ `latest` tag
- ✅ 支持 `linux/amd64` 和 `linux/arm64` 架构

### 本地验证

```bash
# 验证镜像架构
docker buildx imagetools inspect your-username/tradingagents-backend:latest

# 拉取并运行
docker pull your-username/tradingagents-backend:latest
docker run -d -p 8000:8000 your-username/tradingagents-backend:latest
```

---

## 🎯 后续使用

### 发布新版本

```bash
# 1. 开发和测试代码
# ...

# 2. 提交更改
git add .
git commit -m "feat: 新功能"
git push

# 3. 创建新版本 tag
git tag v1.0.2
git push origin v1.0.2

# 4. GitHub Actions 自动构建和发布 ✨
```

### 手动触发构建

1. 访问 GitHub 仓库 → **Actions**
2. 选择 **Docker Publish to Docker Hub**
3. 点击 **Run workflow**
4. 选择分支并点击 **Run workflow**

---

## 📊 构建时间

| 构建类型 | 预计时间 |
|---------|---------|
| 首次构建 | 30-50 分钟 |
| 后续构建（有缓存） | 15-25 分钟 |
| 仅 amd64 | 8-12 分钟 |

---

## 🐛 常见问题

### Q: 构建失败：unauthorized

**解决**：检查 GitHub Secrets 中的 `DOCKERHUB_USERNAME` 和 `DOCKERHUB_TOKEN` 是否正确

### Q: 构建很慢

**原因**：ARM 架构通过 QEMU 模拟，首次构建较慢  
**解决**：等待完成，后续构建会利用缓存加速

### Q: 如何只构建 amd64？

编辑 `.github/workflows/docker-publish.yml`，将 `platforms: linux/amd64,linux/arm64` 改为 `platforms: linux/amd64`

---

## 📚 详细文档

- [完整设置指南](./GITHUB_ACTIONS_SETUP.md)
- [性能优化指南](./MULTIARCH_BUILD_OPTIMIZATION.md)
- [多架构构建通用指南](./MULTIARCH_BUILD.md)

---

## 🎉 完成！

现在您已经设置好 GitHub Actions 自动构建，每次推送 tag 都会自动构建和发布多架构 Docker 镜像！

**优势**：
- ✅ 自动化发布，无需手动构建
- ✅ 支持 amd64 和 arm64 架构
- ✅ 利用 GitHub Actions 缓存加速
- ✅ 不占用本地服务器资源
- ✅ 免费使用（公开仓库）

Happy Coding! 🚀

