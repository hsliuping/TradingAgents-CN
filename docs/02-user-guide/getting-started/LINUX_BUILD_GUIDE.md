# Linux服务器构建和发布Docker镜像指南

本指南介绍如何在Linux服务器上构建和发布TradingAgents-CN的Docker镜像到Docker Hub。

## 前置要求

- Linux服务器（Ubuntu 20.04+、Debian 11+、CentOS 8+等）
- 至少4GB内存（推荐8GB+）
- 至少20GB可用磁盘空间
- 稳定的网络连接
- Docker Hub账号

## 快速开始

### 一键构建和发布

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/TradingAgents-CN.git
cd TradingAgents-CN
git checkout v1.0.0-preview

# 2. 添加执行权限
chmod +x scripts/build-and-publish-linux.sh

# 3. 运行脚本
./scripts/build-and-publish-linux.sh YOUR_DOCKERHUB_USERNAME
```

脚本会自动完成：
- ✅ 检查环境（Docker、Git）
- ✅ 构建后端和前端镜像
- ✅ 登录Docker Hub
- ✅ 标记镜像
- ✅ 推送镜像到Docker Hub

## 详细步骤

### 步骤1：安装Docker

#### Ubuntu/Debian

```bash
# 更新包索引
sudo apt-get update

# 安装必要的包
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# 添加Docker官方GPG密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 设置稳定版仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
sudo docker run hello-world
```

#### CentOS/RHEL

```bash
# 安装必要的包
sudo yum install -y yum-utils

# 添加Docker仓库
sudo yum-config-manager \
    --add-repo \
    https://download.docker.com/linux/centos/docker-ce.repo

# 安装Docker Engine
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
sudo docker run hello-world
```

#### 将当前用户添加到docker组

```bash
# 添加用户到docker组（避免每次都用sudo）
sudo usermod -aG docker $USER

# 重新登录或运行以下命令使更改生效
newgrp docker

# 验证
docker ps
```

### 步骤2：安装Git

```bash
# Ubuntu/Debian
sudo apt-get install -y git

# CentOS/RHEL
sudo yum install -y git

# 验证安装
git --version
```

### 步骤3：克隆代码仓库

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/TradingAgents-CN.git
cd TradingAgents-CN

# 切换到v1.0.0-preview分支
git checkout v1.0.0-preview

# 查看当前分支和最新提交
git branch
git log --oneline -5
```

### 步骤4：配置Docker镜像加速（国内服务器推荐）

如果你的服务器在中国大陆，建议配置镜像加速：

```bash
# 创建Docker配置目录
sudo mkdir -p /etc/docker

# 配置镜像加速
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.ccs.tencentyun.com"
  ]
}
EOF

# 重启Docker服务
sudo systemctl daemon-reload
sudo systemctl restart docker

# 验证配置
docker info | grep -A 5 "Registry Mirrors"
```

### 步骤5：构建Docker镜像

#### 方式1：使用自动化脚本（推荐）

```bash
# 添加执行权限
chmod +x scripts/build-and-publish-linux.sh

# 运行脚本
./scripts/build-and-publish-linux.sh YOUR_DOCKERHUB_USERNAME v1.0.0-preview
```

#### 方式2：手动构建

```bash
# 构建后端镜像
docker build -f Dockerfile.backend -t tradingagents-backend:v1.0.0-preview .

# 构建前端镜像
docker build -f Dockerfile.frontend -t tradingagents-frontend:v1.0.0-preview .

# 查看构建的镜像
docker images | grep tradingagents
```

### 步骤6：登录Docker Hub

```bash
# 登录Docker Hub
docker login

# 输入你的Docker Hub用户名和密码
# Username: your-username
# Password: your-password
```

### 步骤7：标记和推送镜像

```bash
# 标记后端镜像
docker tag tradingagents-backend:v1.0.0-preview YOUR_DOCKERHUB_USERNAME/tradingagents-backend:v1.0.0-preview
docker tag tradingagents-backend:v1.0.0-preview YOUR_DOCKERHUB_USERNAME/tradingagents-backend:latest

# 标记前端镜像
docker tag tradingagents-frontend:v1.0.0-preview YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:v1.0.0-preview
docker tag tradingagents-frontend:v1.0.0-preview YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:latest

# 推送后端镜像
docker push YOUR_DOCKERHUB_USERNAME/tradingagents-backend:v1.0.0-preview
docker push YOUR_DOCKERHUB_USERNAME/tradingagents-backend:latest

# 推送前端镜像
docker push YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:v1.0.0-preview
docker push YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:latest
```

### 步骤8：验证发布

```bash
# 查看本地镜像
docker images | grep YOUR_DOCKERHUB_USERNAME

# 测试拉取镜像
docker pull YOUR_DOCKERHUB_USERNAME/tradingagents-backend:latest
docker pull YOUR_DOCKERHUB_USERNAME/tradingagents-frontend:latest

# 访问Docker Hub查看
# https://hub.docker.com/repositories/YOUR_DOCKERHUB_USERNAME
```

## 常见问题

### Q: 构建时提示"no space left on device"？

A: 磁盘空间不足。清理Docker缓存：

```bash
# 清理未使用的镜像、容器、网络
docker system prune -a

# 查看磁盘使用情况
df -h
docker system df
```

### Q: 构建很慢或超时？

A: 可能是网络问题。解决方案：

1. 配置Docker镜像加速（见步骤4）
2. 使用代理：
   ```bash
   # 临时设置代理
   export HTTP_PROXY=http://proxy-server:port
   export HTTPS_PROXY=http://proxy-server:port
   
   # 构建时使用代理
   docker build --build-arg HTTP_PROXY=$HTTP_PROXY --build-arg HTTPS_PROXY=$HTTPS_PROXY -f Dockerfile.backend -t tradingagents-backend:v1.0.0-preview .
   ```

### Q: 推送镜像时提示"denied: requested access to the resource is denied"？

A: 权限问题。确保：

1. 已正确登录Docker Hub：`docker login`
2. 镜像名称格式正确：`username/image-name:tag`
3. 有权限推送到该仓库

### Q: 如何查看构建日志？

A: 使用`--progress=plain`参数：

```bash
docker build --progress=plain -f Dockerfile.backend -t tradingagents-backend:v1.0.0-preview .
```

### Q: 如何优化构建速度？

A: 使用BuildKit和缓存：

```bash
# 启用BuildKit
export DOCKER_BUILDKIT=1

# 使用缓存构建
docker build --cache-from YOUR_DOCKERHUB_USERNAME/tradingagents-backend:latest -f Dockerfile.backend -t tradingagents-backend:v1.0.0-preview .
```

## 性能优化建议

### 1. 使用多阶段构建（已实现）

前端Dockerfile已使用多阶段构建，大幅减小镜像大小。

### 2. 清理构建缓存

```bash
# 清理构建缓存
docker builder prune

# 清理所有未使用的资源
docker system prune -a --volumes
```

### 3. 并行构建

```bash
# 同时构建前后端镜像
docker build -f Dockerfile.backend -t tradingagents-backend:v1.0.0-preview . &
docker build -f Dockerfile.frontend -t tradingagents-frontend:v1.0.0-preview . &
wait
```

## 安全建议

1. ✅ 不要在镜像中包含`.env`文件（已配置）
2. ✅ 使用`.dockerignore`排除敏感文件（已配置）
3. ✅ 定期更新基础镜像
4. ✅ 使用Docker Hub Access Token而不是密码
5. ✅ 扫描镜像漏洞：`docker scan YOUR_IMAGE`

## 参考资源

- [Docker官方文档](https://docs.docker.com/)
- [Docker Hub](https://hub.docker.com/)
- [Dockerfile最佳实践](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [.dockerignore文档](https://docs.docker.com/engine/reference/builder/#dockerignore-file)

