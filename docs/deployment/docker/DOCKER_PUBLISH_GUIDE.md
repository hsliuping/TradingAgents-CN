# Docker镜像发布到Docker Hub指南

本指南介绍如何将TradingAgents-CN的Docker镜像发布到Docker Hub。

## 前置要求

1. Docker Hub账号（https://hub.docker.com/signup）
2. Docker已安装并运行
3. 本地已成功构建镜像

## 步骤1：注册Docker Hub账号

如果还没有Docker Hub账号：
1. 访问 https://hub.docker.com/signup
2. 填写用户名、邮箱和密码
3. 验证邮箱
4. 登录Docker Hub

## 步骤2：登录Docker Hub

```powershell
# Windows PowerShell
docker login
```

```bash
# Linux/macOS
docker login
```

输入你的Docker Hub用户名和密码。

或者使用命令行直接登录：

```powershell
# Windows PowerShell
docker login -u YOUR_DOCKERHUB_USERNAME -p YOUR_PASSWORD
```

```bash
# Linux/macOS
docker login -u YOUR_DOCKERHUB_USERNAME -p YOUR_PASSWORD
```

替换：
- `YOUR_DOCKERHUB_USERNAME` - 你的Docker Hub用户名
- `YOUR_PASSWORD` - 你的Docker Hub密码

## 步骤3：标记镜像

```powershell
# 标记后端镜像
docker tag tradingagents-backend:v1.0.0-preview YOUR_DOCKERHUB_USERNAME/tradingagents-backend:v1.0.0-preview
docker tag tradingagents-backend:v1.0.0-preview YOUR_DOCKERHUB_USERNAME/tradingagents-backend:latest

# 标记前端镜像
docker tag tradingagents-frontend:v1.0.0-preview YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:v1.0.0-preview
docker tag tradingagents-frontend:v1.0.0-preview YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:latest
```

## 步骤4：推送镜像到Docker Hub

```powershell
# 推送后端镜像
docker push YOUR_DOCKERHUB_USERNAME/tradingagents-backend:v1.0.0-preview
docker push YOUR_DOCKERHUB_USERNAME/tradingagents-backend:latest

# 推送前端镜像
docker push YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:v1.0.0-preview
docker push YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:latest
```

## 步骤5：在Docker Hub上查看镜像

1. 访问 https://hub.docker.com/repositories/YOUR_DOCKERHUB_USERNAME
2. 你会看到刚刚推送的镜像
3. 点击镜像可以查看详情、标签和拉取命令

## 步骤6：创建docker-compose配置文件

创建一个使用Docker Hub镜像的docker-compose文件：

```yaml
# docker-compose.hub.yml
version: '3.8'

services:
  mongodb:
    image: mongo:4.4
    container_name: tradingagents-mongodb
    restart: unless-stopped
    ports:
      - "27017:27017"
    volumes:
      - tradingagents_mongodb_data_v1:/data/db
    environment:
      TZ: "Asia/Shanghai"
    networks:
      - tradingagents-network
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongo localhost:27017/test --quiet
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: tradingagents-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - tradingagents_redis_data_v1:/data
    environment:
      TZ: "Asia/Shanghai"
    networks:
      - tradingagents-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    image: YOUR_DOCKERHUB_USERNAME/tradingagents-backend:latest
    container_name: tradingagents-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      TZ: "Asia/Shanghai"
      MONGODB_URL: "mongodb://mongodb:27017/tradingagents"
      REDIS_URL: "redis://redis:6379/0"
      DOCKER_CONTAINER: "true"
    depends_on:
      mongodb:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - tradingagents-network

  frontend:
    image: YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:latest
    container_name: tradingagents-frontend
    restart: unless-stopped
    ports:
      - "3000:80"
    environment:
      TZ: "Asia/Shanghai"
      VITE_API_BASE_URL: "http://localhost:8000"
    depends_on:
      - backend
    networks:
      - tradingagents-network

volumes:
  tradingagents_mongodb_data_v1:
    name: tradingagents_mongodb_data_v1
  tradingagents_redis_data_v1:
    name: tradingagents_redis_data_v1

networks:
  tradingagents-network:
    name: tradingagents-network
    driver: bridge
```

## 用户使用指南

用户可以通过以下步骤使用你发布的镜像：

### 1. 拉取镜像

```bash
# 拉取后端镜像
docker pull YOUR_DOCKERHUB_USERNAME/tradingagents-backend:latest

# 拉取前端镜像
docker pull YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:latest
```

### 2. 准备环境文件

**重要**：Docker镜像中**不包含**`.env`文件（出于安全考虑），用户需要自己创建。

创建`.env`文件（参考`.env.example`）：

```bash
cp .env.example .env
# 编辑.env文件，配置必要的环境变量
```

必需的环境变量包括：
- `JWT_SECRET` - JWT密钥
- `OPENAI_API_KEY` - OpenAI API密钥（如果使用OpenAI）
- `DEEPSEEK_API_KEY` - DeepSeek API密钥（如果使用DeepSeek）
- 其他API密钥和配置

### 3. 启动服务

```bash
docker-compose -f docker-compose.hub.yml up -d
```

### 4. 访问服务

- 前端：http://localhost:3000
- 后端API：http://localhost:8000
- API文档：http://localhost:8000/docs

## 自动化发布（GitHub Actions）

创建`.github/workflows/docker-publish.yml`实现自动发布到Docker Hub：

```yaml
name: Docker Publish to Docker Hub

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build-and-push:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Extract metadata for backend
        id: meta-backend
        uses: docker/metadata-action@v5
        with:
          images: ${{ secrets.DOCKERHUB_USERNAME }}/tradingagents-backend
          tags: |
            type=ref,event=tag
            type=raw,value=latest
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}

      - name: Build and push backend image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.backend
          push: true
          tags: ${{ steps.meta-backend.outputs.tags }}
          labels: ${{ steps.meta-backend.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Extract metadata for frontend
        id: meta-frontend
        uses: docker/metadata-action@v5
        with:
          images: ${{ secrets.DOCKERHUB_USERNAME }}/tradingagents-frontend
          tags: |
            type=ref,event=tag
            type=raw,value=latest
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}

      - name: Build and push frontend image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.frontend
          push: true
          tags: ${{ steps.meta-frontend.outputs.tags }}
          labels: ${{ steps.meta-frontend.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**注意**：需要在GitHub仓库设置中添加以下Secrets：
- `DOCKERHUB_USERNAME` - 你的Docker Hub用户名
- `DOCKERHUB_TOKEN` - 你的Docker Hub Access Token（在Docker Hub Settings → Security → New Access Token创建）

## 安全说明

### 环境变量和敏感信息

**重要**：Docker镜像中**不包含**任何敏感信息：

1. ✅ `.env`文件被`.dockerignore`排除，不会打包到镜像中
2. ✅ API密钥、数据库密码等敏感信息需要在运行时通过环境变量注入
3. ✅ 用户需要自己创建`.env`文件或通过docker-compose的`environment`配置

### 不要做的事情

❌ **不要**在Dockerfile中使用`COPY .env`
❌ **不要**在镜像中硬编码API密钥
❌ **不要**将包含敏感信息的配置文件打包到镜像
❌ **不要**在GitHub仓库中提交`.env`文件

### 推荐做法

✅ 使用`env_file`在docker-compose中注入环境变量
✅ 使用Docker Secrets（生产环境）
✅ 使用环境变量管理工具（如Vault、AWS Secrets Manager）
✅ 在`.env.example`中提供配置模板（不包含真实值）

## 镜像大小优化建议

当前镜像大小：
- 后端：~1.8GB
- 前端：~85MB

优化建议：
1. 使用多阶段构建（已实现）
2. 清理pip缓存
3. 只安装生产环境必需的依赖
4. 使用.dockerignore排除不必要的文件

## 常见问题

### Q: 推送镜像时提示权限不足？
A: 确保你已经登录Docker Hub（`docker login`），并且使用的是正确的用户名。

### Q: 镜像推送很慢？
A: 国内用户可能会遇到网络问题。建议：
   - 使用代理
   - 在GitHub Actions中构建和推送（GitHub服务器网络更快）
   - 考虑同时发布到阿里云容器镜像服务

### Q: 如何删除已发布的镜像？
A: 在Docker Hub网站上找到对应的仓库，进入Settings → Delete repository。

### Q: 镜像是否支持多架构（ARM/AMD64）？
A: 当前镜像只支持AMD64。如需支持ARM，需要使用`docker buildx`构建多架构镜像。

### Q: 如何创建Docker Hub Access Token？
A: 访问 Docker Hub → Account Settings → Security → New Access Token，创建token后在GitHub Secrets中使用。

## 参考链接

- [Docker Hub官方文档](https://docs.docker.com/docker-hub/)
- [Docker官方文档](https://docs.docker.com/)
- [GitHub Actions文档](https://docs.github.com/en/actions)

