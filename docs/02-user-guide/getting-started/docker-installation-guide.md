# Docker 安装使用指南（v3.0）

> 用 Docker 一键部署 TradingAgents-CN Pro v3.0，支持 Windows、macOS（含 Apple Silicon）、Linux。

---

## 一、这是什么

TradingAgents-CN 是一个 AI 股票研究平台。你输入股票代码，AI 自动完成基本面、技术面、风险评估，输出一份研究报告。

提供两种部署方式：

- **单容器版（推荐）**：一个镜像打包全部服务（数据库 + 后端 + 前端 + 反向代理），一条命令启动，最适合个人用户。
- **backend 多容器版**：后端与数据库、前端分离，适合需要独立扩展后端或已有自建数据库的场景。

本文档以单容器版为主。

> ⚠️ 本系统是研究辅助工具，所有输出仅供研究参考，**不构成投资建议**。当前仅支持 A 股市场。

---

## 二、前置要求

| 项目 | 要求 |
|------|------|
| Docker | Docker Desktop 4.x+（Windows/macOS）或 Docker Engine 20.10+（Linux） |
| 内存 | 至少 8GB（推荐 16GB） |
| 磁盘 | 至少 20GB 可用空间 |
| 网络 | 首次配置模型和数据源时需要联网 |

### 安装 Docker

- **Windows / macOS**：到 [Docker 官网](https://www.docker.com/products/docker-desktop) 下载安装 Docker Desktop，安装后启动它。
- **Linux**：

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl start docker
```

验证安装：

```bash
docker --version
```

---

## 三、快速开始（单容器版）

镜像已发布到 Docker Hub，支持 **amd64 + arm64 双架构**，`docker` 会自动匹配你的机器（Mac Apple Silicon 自动用 arm64，Intel/Windows/Linux 自动用 amd64），无需手动选择。

### 1. 启动容器

**Linux / macOS：**

```bash
docker run -d \
  --name tradingagents \
  --restart unless-stopped \
  -p 8082:8082 \
  -v ta-data:/data/db \
  -v ta-redis:/var/lib/redis \
  -v ta-runtime:/app/runtime \
  -v ta-logs:/app/logs \
  -v ta-qdrant:/app/data \
  -e MONGODB_PASSWORD=换成你自己的密码 \
  -e TZ=Asia/Shanghai \
  hsliup/tradingagents-cn-pro:3-latest
```

**Windows（PowerShell，单行）：**

```powershell
docker run -d --name tradingagents --restart unless-stopped -p 8082:8082 -v ta-data:/data/db -v ta-redis:/var/lib/redis -v ta-runtime:/app/runtime -v ta-logs:/app/logs -v ta-qdrant:/app/data -e MONGODB_PASSWORD=换成你自己的密码 -e TZ=Asia/Shanghai hsliup/tradingagents-cn-pro:3-latest
```

> 说明：`MONGODB_PASSWORD` 是数据库密码，首次启动时设置，**之后不要更改**。建议换成自己的强密码。

### 2. 等待启动

首次启动需要初始化数据库、导入默认配置，约 1~2 分钟。查看状态：

```bash
docker ps
# 状态显示 Up (healthy) 即就绪
```

### 3. 访问系统

浏览器打开 **http://localhost:8082**

默认管理员账号：

- 用户名：`admin`
- 密码：`admin123`

看到登录页面即部署成功。

---

## 四、首次登录后建议配置

1. **修改默认密码**：登录后到「设置」中修改 admin 密码。
2. **配置大模型 API Key**：到「设置 → 模型配置」填入至少一个可用的 LLM API Key（如 DeepSeek、阿里云百炼等）。
3. **配置数据源**：到「设置」中填入 Tushare Token（用于获取 A 股行情和财务数据）。
4. **跑一次分析验证**：进入「单股研究」，输入一个股票代码（如 `600519`），做一次小范围分析，确认链路正常。

> 未配置 API Key 前，容器日志会出现 API Key 相关的报错，属正常现象，配置后即消失。

---

## 五、常用操作

### 查看日志

```bash
docker logs -f tradingagents
```

### 停止 / 启动 / 重启

```bash
docker stop tradingagents
docker start tradingagents
docker restart tradingagents
```

### 查看数据卷

```bash
docker volume ls | grep ta-
```

### 卸载（删除容器与数据，谨慎操作）

```bash
docker rm -f tradingagents
docker volume rm ta-data ta-redis ta-runtime ta-logs ta-qdrant
```

---

## 六、升级到新版本

```bash
# 1. 拉取最新镜像
docker pull hsliup/tradingagents-cn-pro:3-latest

# 2. 用新镜像重建容器（数据卷保留，数据不丢）
docker stop tradingagents
docker rm tradingagents
# 重新执行「三、快速开始」里的 docker run 命令即可
```

---

## 七、常见问题

### 端口 8082 被占用

修改宿主机端口映射，例如改为 `18082`：

```bash
-p 18082:8082
```

然后访问 http://localhost:18082。

### 容器频繁重启 / 内存不足

单容器版内含数据库、后端、前端多个服务，建议给 Docker Desktop 分配至少 8GB 内存：

- Docker Desktop → Settings → Resources → Memory → 调到 8GB 以上。

### 无法访问页面

1. 确认容器状态为 `Up`：`docker ps`
2. 查看日志：`docker logs tradingagents`
3. 首次启动需等 1~2 分钟，稍后再试。

### 如何确认拉取的是哪个架构

```bash
docker inspect hsliup/tradingagents-cn-pro:3-latest --format '{{.Architecture}}'
# Mac Apple Silicon 返回 arm64，Intel/Windows/Linux 返回 amd64
```

---

## 八、免责声明

TradingAgents-CN 是 AI 研究辅助工具，生成的报告、决策标签等所有内容均为 AI 自动生成的研究结论，仅供学习研究参考，**不构成任何投资建议**。股市有风险，投资需谨慎。
