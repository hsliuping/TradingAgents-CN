# Docker Compose 编译版使用说明

## 问题：403 Forbidden 错误

当执行 `docker-compose pull` 时出现 403 错误，通常是因为：
- Docker Hub 上不存在这些镜像
- 镜像未公开或需要认证
- 镜像尚未构建和推送

## 解决方案

### 方案 1：本地构建镜像（推荐）

由于 `docker-compose.compiled.yml` 已经配置了 `build` 指令，直接使用构建命令：

```bash
# 构建所有服务（包括 backend 和 frontend）
docker-compose -f docker-compose.compiled.yml build

# 构建并启动服务
docker-compose -f docker-compose.compiled.yml up -d
```

### 方案 2：使用构建脚本

如果使用编译版，可以使用专门的构建脚本：

```bash
# 进入 docker 目录
cd docker

# 构建编译版镜像（不推送）
./scripts/build-compile.sh

# 或者构建并推送到 Docker Hub（需要先登录）
docker login
./scripts/build-compile.sh --push
```

### 方案 3：先构建后拉取

如果镜像已经推送到 Docker Hub：

```bash
# 1. 先构建镜像
docker-compose -f docker-compose.compiled.yml build

# 2. 推送到 Docker Hub（需要先登录）
docker login
docker push hsliup/tradingagents-pro-backend:latest
docker push hsliup/tradingagents-pro-frontend:latest

# 3. 之后就可以使用 pull 了
docker-compose -f docker-compose.compiled.yml pull
```

## 注意事项

1. **不要使用 `pull`**：如果镜像不存在，直接使用 `build` 命令
2. **构建时间**：首次构建可能需要较长时间（下载依赖、编译代码等）
3. **网络问题**：如果构建时遇到网络问题，可以配置 Docker 镜像加速器
4. **文档打包规则**：后端镜像不会再复制整个 `docs/` 目录，只会包含 `docs/release_v2.0/` 以及运行时页面必须读取的 API 指南、模板、示例白名单文件

## 快速开始

```bash
# 1. 进入 docker 目录
cd docker

# 2. 复制并配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置必要的环境变量

# 3. 构建并启动服务
docker-compose -f docker-compose.compiled.yml up -d --build

# 4. 查看日志
docker-compose -f docker-compose.compiled.yml logs -f

# 5. 访问服务
# 前端和后端都通过 http://localhost:8082 访问
```
