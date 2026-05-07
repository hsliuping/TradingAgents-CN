# TradingAgents-CN V2.1.0 linux和 Mac 部署指南

## 简介

TradingAgents-CN V2.1.0 提供 Docker 一键部署方案，适用于 Linux 和 macOS 系统。无需手动配置环境，一条命令即可完成全部安装。

部署完成后，你将获得：

- 前端界面：浏览器访问，操作交易策略
- 后端 API：策略引擎与数据处理
- MongoDB 数据库：存储交易数据与配置
- Redis 缓存：加速数据读写

## 系统要求

| 项目 | 最低要求 |
|------|---------|
| 操作系统 | Ubuntu 18.04+、Debian 10+、CentOS 7+、macOS 12+ |
| 内存 | 4GB 以上 |
| 磁盘 | 10GB 以上可用空间 |
| 网络 | 能访问 Docker Hub（hub.docker.com） |

> 如果你的服务器在国内，建议配置 Docker 镜像加速器以提升下载速度。

## 快速开始

### Linux 用户（一行命令部署）

```bash
curl -fsSL https://www.tradingagentscn.com/docker/deploy.sh | bash -s --
```

脚本会自动检查并安装所需依赖（Docker、Docker Compose），然后引导你完成配置。

### macOS 用户

macOS 需要先安装 Docker Desktop，然后再运行部署脚本：

**步骤 1：安装 Docker Desktop**

- 方式 A：访问 [Docker 官网](https://www.docker.com/products/docker-desktop) 下载安装
- 方式 B：使用 Homebrew 安装：`brew install --cask docker`

**步骤 2：启动 Docker Desktop**

从应用程序中打开 Docker Desktop，等待状态栏图标变为稳定状态。

**步骤 3：运行部署脚本**

```bash
curl -fsSL https://www.tradingagentscn.com/docker/deploy.sh | bash -s --
```

## 部署过程详解

运行脚本后，按提示依次完成以下配置：

### 1. 依赖检查

脚本自动检测 Docker 和 Docker Compose 是否已安装。如果缺少依赖，会提示是否自动安装：

- Linux：自动使用官方脚本安装 Docker 和 Docker Compose
- macOS：提示安装 Docker Desktop（Docker Desktop 自带 Compose）

### 2. 端口配置

脚本会依次询问四个端口，直接回车即可使用默认值：

| 服务 | 默认端口 | 说明 |
|------|---------|------|
| Nginx（前端） | 8082 | 浏览器访问的端口 |
| MongoDB | 27017 | 数据库端口 |
| Redis | 6379 | 缓存端口 |
| Backend（后端） | 8000 | API 服务端口 |

> 如果这些端口已被其他服务占用，请输入其他可用端口号。

### 3. 版本选择

输入要部署的版本号，例如 `2.1.0`。直接回车则使用最新版本（latest）。

> 版本号无需加 `v` 前缀，脚本会自动处理。

### 4. 自动下载配置

脚本自动从服务器下载以下配置文件：

- `docker-compose.compiled.yml`：Docker 服务编排文件
- `nginx/nginx-proxy.conf`：Nginx 反向代理配置
- `.env`：环境变量配置

如果配置文件已存在，会询问是否覆盖。

### 5. 启动服务

脚本自动拉取 Docker 镜像并启动所有服务。首次部署需要等待镜像下载完成，取决于网络速度，通常需要 3-10 分钟。

## 部署完成后

脚本运行成功后会显示访问信息：

```
✅ 部署完成！

========================================
  访问信息
========================================
部署版本: v2.1.0
前端地址: http://localhost:8082
后端API:  http://localhost:8082/api
MongoDB:  localhost:27017
Redis:    localhost:6379

默认账号: admin
默认密码: admin123
```

打开浏览器访问 `http://你的服务器IP:8082`，使用默认账号密码登录后，请第一时间修改密码。

## 非交互模式

适用于自动化部署或脚本调用，跳过所有交互提示，使用默认值或命令行参数：

```bash
# 使用默认配置部署最新版
curl -fsSL https://www.tradingagentscn.com/docker/deploy.sh | bash -s -- --non-interactive

# 指定版本号
curl -fsSL https://www.tradingagentscn.com/docker/deploy.sh | bash -s -- --non-interactive --image-tag 2.1.0

# 自定义端口
curl -fsSL https://www.tradingagentscn.com/docker/deploy.sh | bash -s -- --non-interactive --nginx-port 9090 --mongodb-port 27018
```

所有可用参数：

| 参数 | 说明 |
|------|------|
| `--non-interactive` | 非交互模式 |
| `--image-tag TAG` | 指定版本号，如 `2.1.0` |
| `--nginx-port PORT` | 前端端口，默认 8082 |
| `--mongodb-port PORT` | 数据库端口，默认 27017 |
| `--redis-port PORT` | 缓存端口，默认 6379 |
| `--backend-port PORT` | 后端端口，默认 8000 |

## 日常运维

以下命令在部署目录下执行：

### 查看服务状态

```bash
docker compose -f docker-compose.compiled.yml ps
```

### 查看实时日志

```bash
# 查看所有服务日志
docker compose -f docker-compose.compiled.yml logs -f

# 查看指定服务日志
docker compose -f docker-compose.compiled.yml logs -f backend
docker compose -f docker-compose.compiled.yml logs -f frontend
```

### 停止服务

```bash
docker compose -f docker-compose.compiled.yml down
```

### 重启服务

```bash
docker compose -f docker-compose.compiled.yml restart
```

### 更新到新版本

重新运行部署脚本，输入新版本号即可。脚本会自动清理旧容器、拉取新镜像、启动服务：

```bash
curl -fsSL https://www.tradingagentscn.com/docker/deploy.sh | bash -s --
```

## 常见问题

### Q：Docker 镜像下载很慢怎么办？

配置 Docker 镜像加速器。编辑 `/etc/docker/daemon.json`（Linux）：

```json
{
  "registry-mirrors": ["https://你的镜像加速地址"]
}
```

然后重启 Docker：`systemctl restart docker`

常见的国内镜像加速器可咨询你的云服务商。

### Q：端口被占用怎么办？

运行脚本时输入其他可用端口号，或者使用非交互模式指定端口：

```bash
curl -fsSL https://www.tradingagentscn.com/docker/deploy.sh | bash -s -- --nginx-port 9090
```

### Q：如何查看服务是否正常运行？

```bash
docker compose -f docker-compose.compiled.yml ps
```

所有服务状态显示 `running` 或 `Up` 即为正常。

### Q：如何重置到初始状态？

```bash
# 停止并删除所有容器和数据卷
docker compose -f docker-compose.compiled.yml down -v

# 重新运行部署脚本
curl -fsSL https://www.tradingagentscn.com/docker/deploy.sh | bash -s --
```

> 注意：`-v` 会删除数据库数据，请提前备份。

### Q：macOS 上提示 "Docker 服务未运行"？

确保 Docker Desktop 应用已启动。检查状态栏是否有 Docker 鲸鱼图标，图标稳定表示 Docker 已就绪。

### Q：服务器重启后服务会自动启动吗？

Docker 服务配置了 `restart: unless-stopped` 策略，只要 Docker 服务设为开机自启（Linux 通常默认开启），容器会跟随自动启动。

检查 Docker 开机自启状态：

```bash
systemctl is-enabled docker
```

如果显示 `disabled`，执行：

```bash
systemctl enable docker
```

## 技术支持

如有问题，可通过以下方式获取帮助：

- 官方网站：https://www.tradingagentscn.com
- QQ 群：1079484482

