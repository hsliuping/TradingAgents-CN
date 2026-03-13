# Docker 编译版构建指南

## 📋 概述

TradingAgents-CN Pro 的 Docker 镜像使用**编译后的代码**（`.pyc` 和 `.pyd` 文件）而不是源码，以保护商业代码。

## 🔐 代码保护策略

| 目录 | 保护方式 | 说明 |
|------|---------|------|
| `core/licensing/` | Cython 编译为 `.pyd` | 最强保护（许可证验证模块） |
| `core/` 其他模块 | 字节码编译为 `.pyc` | 标准保护 |
| `app/` | 字节码编译为 `.pyc` | 标准保护 |
| `tradingagents/` | 保留源码 | 开源部分 |

## 🚀 构建流程

### 方式 1: 使用多架构构建脚本（推荐）

**适用场景**: 发布到 Docker Hub，支持 AMD64 和 ARM64

```powershell
# 1. 读取版本号（从 VERSION 文件）
$Version = Get-Content VERSION

# 2. 构建并推送到 Docker Hub
.\scripts\build-multiarch.ps1 -Registry hsliup -Version $Version

# 3. 只构建本地镜像（不推送）
.\scripts\build-multiarch.ps1 -Version $Version
```

**脚本功能**:
- ✅ 自动运行 `build_portable_package.ps1` 编译代码
- ✅ 使用 `Dockerfile.backend.compiled` 构建后端镜像
- ✅ 支持多架构（AMD64 + ARM64）
- ✅ 自动推送到 Docker Hub（如果指定 `-Registry`）

### 方式 2: 使用 AMD64 构建脚本

**适用场景**: 只构建 AMD64 架构（Intel/AMD 处理器）

```powershell
# 构建并推送
.\scripts\build-amd64.ps1 -Registry hsliup -Version v1.0.2

# 只构建本地镜像
.\scripts\build-amd64.ps1 -Version v1.0.2
```

### 方式 3: 使用发布脚本

**适用场景**: 完整的发布流程（编译 + 构建 + 推送）

```powershell
# 完整流程
.\scripts\publish-docker-images.ps1 -DockerHubUsername hsliup -Version v1.0.2

# 跳过编译（使用现有编译产物）
.\scripts\publish-docker-images.ps1 -DockerHubUsername hsliup -Version v1.0.2 -SkipCompile

# 跳过构建（使用现有镜像）
.\scripts\publish-docker-images.ps1 -DockerHubUsername hsliup -Version v1.0.2 -SkipBuild
```

### 方式 4: 手动构建

**适用场景**: 自定义构建流程

```powershell
# 1. 编译代码
.\scripts\deployment\build_portable_package.ps1 -SkipPackage

# 2. 构建 Docker 镜像
docker build -f Dockerfile.backend.compiled -t tradingagents-backend:v1.0.2 .
docker build -f Dockerfile.frontend -t tradingagents-frontend:v1.0.2 .

# 3. 标记镜像
docker tag tradingagents-backend:v1.0.2 hsliup/tradingagents-backend:v1.0.2
docker tag tradingagents-backend:v1.0.2 hsliup/tradingagents-backend:latest

# 4. 推送到 Docker Hub
docker push hsliup/tradingagents-backend:v1.0.2
docker push hsliup/tradingagents-backend:latest
```

## 📦 Dockerfile 说明

### Dockerfile.backend.compiled

**特点**:
- 使用 `release/TradingAgentsCN-portable/` 中的编译后代码
- 不包含源码（除了 `tradingagents/` 开源部分）
- 依赖项从 `pyproject.toml` 安装

**关键步骤**:
```dockerfile
# 1. 安装依赖
COPY pyproject.toml README.md ./
RUN pip install --prefer-binary . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 复制编译后的代码
COPY release/TradingAgentsCN-portable/app ./app
COPY release/TradingAgentsCN-portable/core ./core
COPY release/TradingAgentsCN-portable/tradingagents ./tradingagents

# 3. 复制配置文件
COPY config ./config
COPY scripts ./scripts
COPY install ./install

# 4. 复制运行时文档白名单
RUN mkdir -p /app/docs /app/docs/api/examples /app/docs/examples
COPY docs/release_v2.0/ ./docs/
COPY docs/api/STOCK_DATA_IMPORT_API.md ./docs/api/STOCK_DATA_IMPORT_API.md
COPY docs/api/examples/stock_data_import_examples.py ./docs/api/examples/stock_data_import_examples.py
COPY docs/examples/social_media_api_guide.md ./docs/examples/social_media_api_guide.md
COPY docs/examples/social_media_api_example.py ./docs/examples/social_media_api_example.py
COPY docs/examples/social_media_template.csv ./docs/examples/social_media_template.csv
COPY docs/examples/social_media_template.json ./docs/examples/social_media_template.json
```

说明：Docker 后端镜像不再复制整个 `docs/` 目录，而是对齐桌面安装包规则，只复制 `docs/release_v2.0/` 和运行时接口页面仍会直接读取的白名单文件，避免把内部文档一并带入镜像。

### Dockerfile.backend（旧版 - 已弃用）

**特点**:
- 直接复制源码
- 不提供代码保护
- 仅用于开发测试

## 🔄 使用 docker-compose

### docker-compose.hub.nginx.yml

**配置说明**:
```yaml
backend:
  build:
    context: .
    dockerfile: Dockerfile.backend.compiled  # 使用编译版
  image: hsliup/tradingagents-backend:latest
```

**使用方法**:
```powershell
# 1. 先编译代码
.\scripts\deployment\build_portable_package.ps1 -SkipPackage

# 2. 构建镜像
docker-compose -f docker-compose.hub.nginx.yml build backend

# 3. 启动服务
docker-compose -f docker-compose.hub.nginx.yml up -d
```

## ⚠️ 注意事项

### 1. 编译产物依赖

所有构建脚本都依赖 `release/TradingAgentsCN-portable/` 目录中的编译产物。

**检查编译产物**:
```powershell
# 检查目录是否存在
Test-Path release\TradingAgentsCN-portable

# 检查编译后的文件
Get-ChildItem release\TradingAgentsCN-portable\core\licensing\*.pyd
Get-ChildItem release\TradingAgentsCN-portable\app\*.pyc -Recurse
```

### 2. 版本号管理

**推荐方式**: 使用 `VERSION` 文件统一管理版本号

```powershell
# 读取版本号
$Version = Get-Content VERSION

# 使用版本号构建
.\scripts\build-multiarch.ps1 -Registry hsliup -Version $Version
```

### 3. Docker Hub 认证

**推送镜像前需要登录**:
```powershell
docker login -u hsliup
```

## 📊 构建产物

### 镜像标签

| 镜像 | 标签 | 说明 |
|------|------|------|
| `hsliup/tradingagents-backend` | `v1.0.2` | 版本标签 |
| `hsliup/tradingagents-backend` | `latest` | 最新版本 |
| `hsliup/tradingagents-frontend` | `v1.0.2` | 版本标签 |
| `hsliup/tradingagents-frontend` | `latest` | 最新版本 |

### 镜像大小

- **后端镜像**: ~1.2 GB
- **前端镜像**: ~50 MB

## 🔗 相关文档

- [Docker 部署指南](DOCKER_DEPLOYMENT_v1.0.0.md)
- [便携版打包指南](../../scripts/deployment/README_PRO_PACKAGING.md)
- [Windows 安装包构建](../../scripts/windows-installer/README.md)

---

**最后更新**: 2026-01-06  
**维护者**: TradingAgents-CN Pro Team

