# 🚀 TradingAgents-CN Pro v1.0 Docker 一键部署指南

> 使用一键部署脚本快速部署完整的 AI 股票分析系统（正式版 + 自动初始化）

## 📋 目录

- [系统简介](#系统简介)
- [部署架构](#部署架构)
- [前置要求](#前置要求)
- [快速开始](#快速开始)
- [详细步骤](#详细步骤)
- [配置说明](#配置说明)
- [常见问题](#常见问题)
- [进阶配置](#进阶配置)

---

## 🎯 系统简介

**TradingAgents-CN Pro v1.0** 是一个基于多智能体架构的 AI 股票分析系统，支持：

- 🤖 **15+ AI 模型**：集成国内外主流大语言模型
- 📊 **多维度分析**：基本面、技术面、新闻分析、社媒分析
- 🔄 **实时数据**：支持 AKShare、Tushare、BaoStock 等数据源
- 🎨 **现代化界面**：Vue 3 + Element Plus 前端
- 🐳 **一键部署**：自动化部署脚本，3 分钟完成部署
- 🔒 **代码保护**：编译版镜像，保护核心代码
- ⚡ **自动初始化**：首次启动自动导入配置和创建用户
- 🔧 **端口配置**：部署时可自定义服务端口，避免冲突

### Pro v1.0 版本特性

- ✅ **一键部署脚本**：自动下载配置、创建目录、启动服务
- ✅ **交互式端口配置**：部署时可自定义 Nginx、MongoDB、Redis、Backend 端口
- ✅ **自动数据库初始化**：首次启动自动导入配置数据，无需手动执行
- ✅ **代码保护**：使用编译后的字节码（.pyc）和 Cython 扩展（.pyd/.so）
- ✅ **统一入口**：Nginx 反向代理，前后端通过同一端口访问
- ✅ **向量数据库支持**：集成 Qdrant 向量数据库，提升分析能力

---

## 🏗️ 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Nginx (端口 8082)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  前端静态资源 (/)                                      │   │
│  │  API 反向代理 (/api → backend:8000)                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
┌──────────────────┐                  ┌──────────────────┐
│  Frontend        │                  │  Backend         │
│  (Vue 3)         │                  │  (FastAPI)       │
│  端口: 80        │                  │  端口: 8000      │
│  编译版镜像       │                  │  编译版镜像       │
└──────────────────┘                  └──────────────────┘
                                              ↓
                        ┌─────────────────────┴─────────────────────┐
                        ↓                                           ↓
                ┌──────────────────┐                      ┌──────────────────┐
                │  MongoDB         │                      │  Redis           │
                │  端口: 27017     │                      │  端口: 6379      │
                │  数据持久化      │                      │  缓存加速        │
                └──────────────────┘                      └──────────────────┘
```

**访问方式**：
- 用户只需访问 `http://服务器IP:8082` 即可使用完整系统
- Nginx 自动处理前端页面和 API 请求的路由

---

## 📋 部署流程概览

**⚠️ 请先阅读此部分，了解完整部署流程，避免遗漏关键步骤！**

### 部署步骤总览

```
第一阶段：环境准备（首次部署必做）
├─ 步骤 1：检查系统要求 ✓
├─ 步骤 2：安装 Docker 和 Docker Compose ✓
└─ 步骤 3：验证 Docker 安装 ✓

第二阶段：下载部署文件
├─ 步骤 4：创建项目目录 ✓
├─ 步骤 5：下载 Docker Compose 配置文件 ✓
│          ⚠️ 使用 docker-compose.compiled.yml（编译版）
├─ 步骤 6：下载环境配置文件 (.env) ✓
└─ 步骤 7：下载 Nginx 配置文件 ✓

第三阶段：配置系统
├─ 步骤 8：配置 API 密钥（至少配置一个 LLM）✓
│          ⚠️ 这是必须步骤，否则无法使用 AI 分析功能
└─ 步骤 9：配置数据源（可选，Tushare/AKShare）✓

第四阶段：启动服务
├─ 步骤 10：拉取 Docker 镜像 ✓
├─ 步骤 11：启动所有容器 ✓
└─ 步骤 12：检查服务状态 ✓

第五阶段：自动初始化（v2.0 新特性）
└─ 步骤 13：系统自动初始化 ✓
           ⚠️ v2.0 版本首次启动会自动导入配置和创建用户
           ⚠️ 无需手动执行初始化脚本

第六阶段：访问系统
└─ 步骤 14：浏览器访问并登录 ✓
```

### 各步骤详细说明

| 步骤 | 名称 | 作用 | 是否必须 | 预计耗时 |
|------|------|------|---------|---------|
| **第一阶段：环境准备** | | | | |
| 1 | 检查系统要求 | 确认硬件和操作系统满足要求 | ✅ 必须 | 1 分钟 |
| 2 | 安装 Docker | 安装容器运行环境 | ✅ 必须（首次） | 5-10 分钟 |
| 3 | 验证 Docker | 确认 Docker 正常工作 | ✅ 必须 | 1 分钟 |
| **第二阶段：一键部署** | | | | |
| 4 | 下载部署脚本 | 下载 deploy.sh 或 deploy.ps1 脚本 | ✅ 必须 | 10 秒 |
| 5 | 运行部署脚本 | 脚本自动完成所有配置和部署 | ✅ 必须 | 2-3 分钟 |
| 6 | 配置服务端口 | 交互式配置 Nginx、MongoDB、Redis、Backend 端口 | ✅ 必须 | 30 秒 |
| **第三阶段：自动初始化（Pro v1.0）** | | | | |
| 7 | 自动初始化 | 系统自动导入配置数据和管理员账号 | ✅ 自动执行 | 30-60 秒 |
| **第四阶段：访问和配置** | | | | |
| 8 | 浏览器访问 | 打开浏览器访问系统并登录 | ✅ 必须 | 1 分钟 |
| 9 | 配置 AI 模型 | 在管理界面配置 LLM API 密钥 | ✅ 必须 | 2-5 分钟 |
| 10 | 配置数据源 | 在管理界面配置 Tushare Token 等 | ⚠️ 可选 | 2 分钟 |
```

### ⚠️ 最容易遗漏的步骤

**请特别注意以下步骤，这些是用户最容易遗漏的：**

#### 1. ❌ 忘记配置 AI 模型（步骤 9）

**后果**：系统可以启动，但无法使用 AI 分析功能，会提示 "API 密钥未配置"

**解决**：
- 登录系统后，进入"系统管理 → LLM 配置"页面
- 配置至少一个 AI 模型的 API 密钥
- 推荐配置：阿里百炼（国内速度快）或 DeepSeek（性价比高）

#### 2. ❌ 端口冲突（步骤 6）

**后果**：部署脚本报错，提示端口已被占用

**解决**：
- 部署脚本会提示配置端口
- 输入未被占用的端口号
- 或停止占用端口的其他服务

#### 3. ❌ 没有验证 Docker 安装（步骤 3）

**后果**：后续所有步骤全部失败

**解决**：
```bash
# 运行以下命令验证
docker --version
docker compose version
docker ps
```

#### 4. ❌ 忘记等待自动初始化完成（步骤 7）

**后果**：登录时提示"用户不存在"或"密码错误"

**解决**：
```bash
# 查看初始化日志
docker-compose -f docker-compose.compiled.yml logs backend | grep -i "初始化\|init\|import"

# 等待看到 "✅ 自动初始化完成" 提示
# 如果初始化失败，手动执行
docker exec -it tradingagents-backend-pro python scripts/import_config_and_create_user.py \
    install/database_export_config_2026-01-05.json --host --overwrite
```

### 📞 遇到问题？

如果部署过程中遇到问题，请：

1. 先查看本文档的 [常见问题](#常见问题) 章节
2. 检查 Docker 容器日志：`docker logs tradingagents-backend-pro`
3. 确认是否遗漏了上述关键步骤
4. 查看部署脚本输出的错误信息

---

## ✅ 前置要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 20 GB | 50 GB+ |
| 网络 | 10 Mbps | 100 Mbps+ |

### 软件要求

- **操作系统**：
  - Windows 10+ (推荐 Windows 11)
  - Linux (Ubuntu 20.04+, CentOS 7+)
  - macOS (Intel 或 Apple Silicon M1/M2/M3)
- **Docker**：20.10+
- **Docker Compose**：2.0+

**如果尚未安装 Docker 和 Docker Compose，请参考下方的 [Docker 安装指南](#docker-安装指南)**

### 验证安装

```bash
# 检查 Docker 版本
docker --version
# 输出示例: Docker version 24.0.7, build afdd53b

# 检查 Docker Compose 版本
docker-compose --version
# 输出示例: Docker Compose version v2.23.0

# 检查 Docker 服务状态
docker ps
# 应该能正常列出容器（即使为空）
```

---

## 🚀 快速开始

### 一键部署（3 分钟）

#### Windows 用户（推荐）

**使用一键部署脚本，自动完成所有配置！**

```powershell
# 1. 下载部署脚本
Invoke-WebRequest -Uri "https://www.tradingagentscn.com/docker/deploy.ps1" -OutFile "deploy.ps1"

# 2. 运行部署脚本
.\deploy.ps1

# 脚本会自动完成以下操作：
# ✅ 检查 Docker 和 docker-compose 是否安装
# ✅ 询问并配置服务端口（Nginx、MongoDB、Redis、Backend）
# ✅ 下载 docker-compose.compiled.yml 配置文件
# ✅ 下载 Nginx 配置文件
# ✅ 创建必需的目录
# ✅ 配置环境变量文件 (.env)
# ✅ 启动所有 Docker 服务
# ✅ 显示访问信息

# 3. 访问系统
# 浏览器打开: http://localhost:{你配置的端口} （默认 8082）
# 默认账号: admin / admin123
# ⚠️ 登录后请立即修改默认密码！

# 4. 配置 AI 模型（登录后在管理界面配置）
# 登录系统后，进入"系统管理 → LLM 配置"页面
# 配置至少一个 AI 模型的 API 密钥：
#   - 阿里百炼（推荐，国内速度快）
#   - DeepSeek（推荐，性价比高）
#   - OpenAI、Google Gemini 等其他模型
# 配置数据源（可选）：
#   - Tushare Token（专业金融数据）
#   - 其他数据源配置
```

**💡 提示**：
- 如果执行脚本时提示权限不足，请以管理员身份运行 PowerShell
- Windows 11 用户推荐使用 Windows Terminal，体验更好
- 部署过程中可以自定义端口，避免与现有服务冲突

#### Linux 用户

**使用一键部署脚本，自动完成所有配置！**

```bash
# 1. 下载部署脚本
wget https://www.tradingagentscn.com/docker/deploy.sh

# 2. 添加执行权限
chmod +x deploy.sh

# 3. 运行部署脚本
./deploy.sh

# 脚本会自动完成以下操作：
# ✅ 检查 Docker 和 docker-compose 是否安装
# ✅ 询问并配置服务端口（Nginx、MongoDB、Redis、Backend）
# ✅ 下载 docker-compose.compiled.yml 配置文件
# ✅ 下载 Nginx 配置文件
# ✅ 创建必需的目录
# ✅ 配置环境变量文件 (.env)
# ✅ 启动所有 Docker 服务
# ✅ 显示访问信息

# 4. 访问系统
# 浏览器打开: http://localhost:{你配置的端口} （默认 8082）
# 或: http://你的服务器IP:{你配置的端口}
# 默认账号: admin / admin123
# ⚠️ 登录后请立即修改默认密码！

# 5. 配置 AI 模型（登录后在管理界面配置）
# 登录系统后，进入"系统管理 → LLM 配置"页面
# 配置至少一个 AI 模型的 API 密钥：
#   - 阿里百炼（推荐，国内速度快）
#   - DeepSeek（推荐，性价比高）
#   - OpenAI、Google Gemini 等其他模型
# 配置数据源（可选）：
#   - Tushare Token（专业金融数据）
#   - 其他数据源配置
```

#### macOS 用户

**Apple Silicon (M1/M2/M3)** 和 **Intel 芯片** 都使用相同的命令（Docker 会自动选择正确的架构）：

**使用一键部署脚本，自动完成所有配置！**

```bash
# 1. 下载部署脚本
curl -O https://www.tradingagentscn.com/docker/deploy.sh

# 2. 添加执行权限
chmod +x deploy.sh

# 3. 运行部署脚本
./deploy.sh

# 脚本会自动完成以下操作：
# ✅ 检查 Docker 和 docker-compose 是否安装
# ✅ 询问并配置服务端口（Nginx、MongoDB、Redis、Backend）
# ✅ 下载 docker-compose.compiled.yml 配置文件
# ✅ 下载 Nginx 配置文件
# ✅ 创建必需的目录
# ✅ 配置环境变量文件 (.env)
# ✅ 启动所有 Docker 服务
# ✅ 显示访问信息

# 4. 访问系统
# 浏览器打开: http://localhost:{你配置的端口} （默认 8082）
# 默认账号: admin / admin123
# ⚠️ 登录后请立即修改默认密码！

# 5. 配置 AI 模型（登录后在管理界面配置）
# 登录系统后，进入"系统管理 → LLM 配置"页面
# 配置至少一个 AI 模型的 API 密钥：
#   - 阿里百炼（推荐，国内速度快）
#   - DeepSeek（推荐，性价比高）
#   - OpenAI、Google Gemini 等其他模型
# 配置数据源（可选）：
#   - Tushare Token（专业金融数据）
#   - 其他数据源配置
```

---

## 📖 详细步骤

### 步骤 1：准备服务器

#### Linux 服务器

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y  # Ubuntu/Debian
# 或
sudo yum update -y  # CentOS/RHEL

# 安装 Docker
curl -fsSL https://get.docker.com | bash -s docker

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户添加到 docker 组（避免每次使用 sudo）
sudo usermod -aG docker $USER
# 注销并重新登录以使更改生效
```

#### Windows 服务器

1. 下载并安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 启动 Docker Desktop
3. 打开 PowerShell（管理员模式）

#### macOS

1. 下载并安装 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
   - **Apple Silicon (M1/M2/M3)**：选择 "Apple Chip" 版本
   - **Intel 芯片**：选择 "Intel Chip" 版本
2. 启动 Docker Desktop
3. 打开终端

### 步骤 2：使用一键部署脚本

**所有平台都使用一键部署脚本，无需手动配置！**

请参考上面的"快速开始"部分，使用对应平台的一键部署脚本：
- **Windows**: 使用 `deploy.ps1`
- **Linux**: 使用 `deploy.sh`
- **macOS**: 使用 `deploy.sh`

脚本会自动完成所有配置和部署工作。

**获取 API 密钥**：

| 服务 | 注册地址 | 说明 |
|------|---------|------|
| 阿里百炼 | https://dashscope.aliyun.com/ | 国产模型，中文优化，推荐 |
| DeepSeek | https://platform.deepseek.com/ | 性价比高，推荐 |
| OpenAI | https://platform.openai.com/ | 需要国外网络 |
| Tushare | https://tushare.pro/weborder/#/login?reg=tacn | 专业金融数据 |

### 步骤 4：启动服务

#### Windows 用户（PowerShell）

```powershell
# 拉取最新镜像
docker-compose -f docker-compose.compiled.yml pull

# 启动所有服务（后台运行）
docker-compose -f docker-compose.compiled.yml up -d

# 查看服务状态
docker-compose -f docker-compose.compiled.yml ps
```

#### Linux 用户

```bash
# 拉取最新镜像
docker-compose -f docker-compose.compiled.yml pull

# 启动所有服务（后台运行）
docker-compose -f docker-compose.compiled.yml up -d

# 查看服务状态
docker-compose -f docker-compose.compiled.yml ps
```

#### macOS 用户

```bash
# 拉取最新镜像
docker-compose -f docker-compose.compiled.yml pull

# 启动所有服务（后台运行）
docker-compose -f docker-compose.compiled.yml up -d

# 查看服务状态
docker-compose -f docker-compose.compiled.yml ps
```

**预期输出**：

```
NAME                       IMAGE                                    STATUS
tradingagents-backend-pro  hsliup/tradingagents-pro-backend:latest  Up (healthy)
tradingagents-frontend-pro hsliup/tradingagents-pro-frontend:latest Up (healthy)
tradingagents-mongodb-propro mongo:4.4                             Up (healthy)
tradingagents-nginx-pro    nginx:alpine                             Up
tradingagents-redis-pro    redis:7-alpine                            Up (healthy)
```

**Windows 用户注意事项**：
- 如果遇到 "docker-compose: command not found"，请使用 `docker compose`（不带连字符）
- 确保 Docker Desktop 已启动并运行
- 如果遇到端口占用（8082 端口），请检查是否有其他程序占用该端口

### 步骤 5：验证自动初始化（v2.0 新特性）

**v2.0 版本首次启动会自动执行初始化**，无需手动执行脚本。

#### 查看初始化日志

**Windows 用户（PowerShell）**：

```powershell
# 查看后端日志中的初始化信息
docker-compose -f docker-compose.compiled.yml logs backend | Select-String -Pattern "初始化|init|import|admin|首次启动"

# 或查看完整日志
docker-compose -f docker-compose.compiled.yml logs backend
```

**Linux/macOS 用户**：

```bash
# 查看后端日志中的初始化信息
docker-compose -f docker-compose.compiled.yml logs backend | grep -i "初始化\|init\|import\|admin\|首次启动"

# 或查看完整日志
docker-compose -f docker-compose.compiled.yml logs backend
```

**预期输出**：

```
tradingagents-backend-pro  | ==========================================
tradingagents-backend-pro  | 🚀 首次启动检测到，开始初始化数据库...
tradingagents-backend-pro  | ==========================================
tradingagents-backend-pro  | 
tradingagents-backend-pro  | ⏳ 等待数据库服务就绪...
tradingagents-backend-pro  | ✅ MongoDB 连接成功
tradingagents-backend-pro  | ✅ Redis 连接成功
tradingagents-backend-pro  | 
tradingagents-backend-pro  | 📦 开始导入配置数据并创建默认用户...
tradingagents-backend-pro  |    使用配置文件: /app/install/database_export_config_2025-10-17.json
tradingagents-backend-pro  | ✅ 数据库初始化完成！
tradingagents-backend-pro  | 📋 默认登录信息:
tradingagents-backend-pro  |    用户名: admin
tradingagents-backend-pro  |    密码: admin123
tradingagents-backend-pro  |    ⚠️  请首次登录后立即修改密码！
```

#### 验证初始化是否成功

```bash
# 检查标记文件是否存在
docker exec tradingagents-backend-pro ls -la /app/runtime/.config_imported

# 如果文件存在，说明初始化成功
# 如果文件不存在，需要手动执行初始化（见下方）
```

#### 如果自动初始化失败

如果自动初始化失败，可以手动执行：

```bash
# 手动执行初始化脚本
docker exec -it tradingagents-backend-pro python scripts/import_config_and_create_user.py

# 或强制重新初始化
docker exec -it tradingagents-backend-pro python scripts/import_config_and_create_user.py --overwrite
```

**说明**：
- v2.0 版本会自动检测首次启动并执行初始化
- 如果标记文件 `/app/runtime/.config_imported` 存在，会跳过初始化
- 无需手动下载配置文件，所有配置都内置在 Docker 镜像中

### 步骤 6：访问系统

打开浏览器，访问：

#### Windows 本地部署

```
http://localhost:8082
```

#### 服务器部署

```
http://你的服务器IP:8082
```

**默认登录信息**：
- 用户名：`admin`
- 密码：`admin123`

**首次登录后建议**：
1. ✅ 修改默认密码（设置 → 个人设置 → 修改密码）
2. ✅ 检查 LLM 配置是否正确（设置 → 系统配置 → LLM 提供商）
3. ✅ 测试运行一个简单的分析任务（分析 → 单股分析）
4. ✅ 配置数据源（设置 → 系统配置 → 数据源配置）

**Windows 用户常见问题**：
- 如果无法访问 `http://localhost:8082`，请检查 Docker Desktop 是否正常运行
- 如果提示端口占用，请检查 8082 端口是否被其他程序占用
- 可以使用 `netstat -ano | findstr :8082` 查看端口占用情况

---

## ⚙️ 配置说明

### 目录结构

#### Windows 用户

```
C:\Users\你的用户名\tradingagents-demo-v2\
├── docker-compose.compiled.yml  # Docker Compose 配置文件（v2.0 编译版）
├── .env                         # 环境变量配置
├── nginx\
│   └── nginx-proxy.conf        # Nginx 配置文件
├── logs\                       # 日志目录（自动创建）
├── data\                       # 数据目录（自动创建）
├── runtime\                    # 运行时目录（自动创建，包含初始化标记文件）
└── config\                     # 配置目录（自动创建）
```

#### Linux/macOS 用户

```
~/tradingagents-demo-v2/
├── docker-compose.compiled.yml  # Docker Compose 配置文件（v2.0 编译版）
├── .env                         # 环境变量配置
├── nginx/
│   └── nginx-proxy.conf        # Nginx 配置文件
├── logs/                       # 日志目录（自动创建）
├── data/                       # 数据目录（自动创建）
├── runtime/                    # 运行时目录（自动创建，包含初始化标记文件）
└── config/                     # 配置目录（自动创建）
```

**说明**：
- 初始配置数据已内置在 Docker 镜像中，无需手动下载
- `logs/`、`data/`、`runtime/`、`config/` 目录会在首次启动时自动创建
- `runtime/.config_imported` 文件用于标记是否已初始化

### 端口说明

| 服务 | 容器内端口 | 宿主机端口 | 说明 |
|------|-----------|-----------|------|
| Nginx | 8082 | 8082 | 统一入口，处理前端和 API |
| Backend | 8000 | - | 内部端口，通过 Nginx 访问 |
| Frontend | 80 | - | 内部端口，通过 Nginx 访问 |
| MongoDB | 27017 | 27017 | 数据库（可选暴露） |
| Redis | 6379 | 6379 | 缓存（可选暴露） |

**注意**：v2.0 版本默认使用 8082 端口，避免与系统服务冲突。

### 数据持久化

系统使用 Docker Volume 和目录挂载持久化数据：

#### Windows 用户

```powershell
# 查看数据卷
docker volume ls | Select-String tradingagents

# 备份数据卷
docker run --rm -v tradingagents_mongodb_data:/data -v ${PWD}:/backup alpine tar czf /backup/mongodb_backup.tar.gz /data

# 恢复数据卷
docker run --rm -v tradingagents_mongodb_data:/data -v ${PWD}:/backup alpine tar xzf /backup/mongodb_backup.tar.gz -C /
```

#### Linux/macOS 用户

```bash
# 查看数据卷
docker volume ls | grep tradingagents

# 备份数据卷
docker run --rm -v tradingagents_mongodb_data:/data -v $(pwd):/backup alpine tar czf /backup/mongodb_backup.tar.gz /data

# 恢复数据卷
docker run --rm -v tradingagents_mongodb_data:/data -v $(pwd):/backup alpine tar xzf /backup/mongodb_backup.tar.gz -C /
```

---

## 🔧 常见问题

### 1. 服务启动失败

**问题**：`docker-compose up` 报错

**解决方案**：

```bash
# 查看详细日志
docker-compose -f docker-compose.compiled.yml logs

# 查看特定服务日志
docker-compose -f docker-compose.compiled.yml logs backend

# 重启服务
docker-compose -f docker-compose.compiled.yml restart
```

### 2. 无法访问系统

**问题**：浏览器无法打开 `http://localhost:8082` 或 `http://服务器IP:8082`

#### Windows 用户检查清单

```powershell
# 1. 检查服务状态
docker-compose -f docker-compose.compiled.yml ps

# 2. 检查端口占用
netstat -ano | findstr :8082

# 3. 检查 Docker Desktop 是否运行
# 打开 Docker Desktop 应用，确保状态为 "Running"

# 4. 如果 8082 端口被占用，修改端口
# 编辑 docker-compose.compiled.yml，将 "8082:8082" 改为 "8080:8082"
# 然后访问 http://localhost:8080
```

#### Linux 用户检查清单

```bash
# 1. 检查服务状态
docker-compose -f docker-compose.compiled.yml ps

# 2. 检查端口占用
sudo netstat -tulpn | grep :8082

# 3. 检查防火墙
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS

# 4. 开放 8082 端口
sudo ufw allow 8082  # Ubuntu
sudo firewall-cmd --add-port=8082/tcp --permanent && sudo firewall-cmd --reload  # CentOS
```

#### macOS 用户检查清单

```bash
# 1. 检查服务状态
docker-compose -f docker-compose.compiled.yml ps

# 2. 检查端口占用
lsof -i :8082

# 3. 检查 Docker Desktop 是否运行
# 打开 Docker Desktop 应用，确保状态为 "Running"

# 4. 如果 8082 端口被占用，修改端口
# 编辑 docker-compose.compiled.yml，将 "8082:8082" 改为 "8080:8082"
# 然后访问 http://localhost:8080
```

### 3. 自动初始化失败

**问题**：日志显示初始化失败，无法登录系统

**解决方案**：

```bash
# 1. 查看详细初始化日志
docker-compose -f docker-compose.compiled.yml logs backend | grep -i "初始化\|init\|import\|error"

# 2. 检查 MongoDB 是否正常运行
docker-compose -f docker-compose.compiled.yml ps mongodb

# 3. 手动执行初始化脚本
docker exec -it tradingagents-backend-pro python scripts/import_config_and_create_user.py

# 4. 如果仍然失败，检查标记文件
docker exec tradingagents-backend-pro ls -la /app/runtime/.config_imported

# 5. 强制重新初始化（删除标记文件）
docker exec tradingagents-backend-pro rm /app/runtime/.config_imported
docker-compose -f docker-compose.compiled.yml restart backend
```

### 4. API 请求失败

**问题**：前端显示"网络错误"或"API 请求失败"

#### Windows 用户解决方案

```powershell
# 检查后端日志
docker logs tradingagents-backend-pro

# 检查 Nginx 日志
docker logs tradingagents-nginx-pro

# 测试后端健康检查（使用 PowerShell）
Invoke-WebRequest -Uri "http://localhost:8000/api/health"

# 或使用 curl（如果已安装）
curl http://localhost:8000/api/health
```

#### Linux/macOS 用户解决方案

```bash
# 检查后端日志
docker logs tradingagents-backend-pro

# 检查 Nginx 日志
docker logs tradingagents-nginx-pro

# 测试后端健康检查
curl http://localhost:8000/api/health
```

### 5. 数据库连接失败

**问题**：后端日志显示"MongoDB connection failed"

**解决方案**：

```bash
# 检查 MongoDB 状态
docker exec -it tradingagents-mongodb-propro mongo -u admin -p tradingagents123 --authenticationDatabase admin

# 重启 MongoDB
docker-compose -f docker-compose.compiled.yml restart mongodb

# 检查数据卷
docker volume inspect tradingagents_mongodb_data
```

### 6. 内存不足

**问题**：系统运行缓慢或容器被杀死

#### Windows 用户解决方案

```powershell
# 查看资源使用情况
docker stats

# 清理未使用的资源
docker system prune -a

# 调整 Docker Desktop 内存限制
# 1. 打开 Docker Desktop
# 2. 点击 Settings → Resources → Advanced
# 3. 调整 Memory 滑块（推荐至少 4GB）
# 4. 点击 Apply & Restart

# 限制容器内存（编辑 docker-compose.compiled.yml）
# 使用记事本或 VS Code 打开文件，添加：
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

#### Linux/macOS 用户解决方案

```bash
# 查看资源使用情况
docker stats

# 清理未使用的资源
docker system prune -a

# 限制容器内存（编辑 docker-compose.compiled.yml）
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

---

## 🎓 进阶配置

### 使用自定义域名

编辑 `nginx/nginx-proxy.conf`：

```nginx
server {
    listen 8082;
    server_name your-domain.com;  # 修改为你的域名
    
    # ... 其他配置保持不变
}
```

配置 DNS 解析，将域名指向服务器 IP，然后重启 Nginx：

```bash
docker-compose -f docker-compose.compiled.yml restart nginx
```

### 启用 HTTPS

1. 获取 SSL 证书（推荐使用 Let's Encrypt）：

```bash
# 安装 certbot
sudo apt install certbot

# 获取证书
sudo certbot certonly --standalone -d your-domain.com
```

2. 修改 `nginx/nginx-proxy.conf`：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # ... 其他配置
}

# HTTP 重定向到 HTTPS
server {
    listen 8082;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

3. 挂载证书目录并重启：

```yaml
# docker-compose.compiled.yml
services:
  nginx:
    volumes:
      - ./nginx/nginx-proxy.conf:/etc/nginx/conf.d/default.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

### 性能优化

#### 1. 启用 Redis 持久化

编辑 `docker-compose.compiled.yml`：

```yaml
services:
  redis:
    command: redis-server --appendonly yes --requirepass tradingagents123 --maxmemory 2gb --maxmemory-policy allkeys-lru
```

#### 2. MongoDB 索引优化

```bash
# 进入 MongoDB
docker exec -it tradingagents-mongodb-propro mongo -u admin -p tradingagents123 --authenticationDatabase admin

# 创建索引
use tradingagents
db.market_quotes.createIndex({code: 1, timestamp: -1})
db.stock_basic_info.createIndex({code: 1})
db.analysis_results.createIndex({user_id: 1, created_at: -1})
```

#### 3. 日志轮转

创建 `logrotate` 配置：

```bash
sudo nano /etc/logrotate.d/tradingagents
```

```
/path/to/tradingagents-demo-v2/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

---

## 📊 监控和维护

### 查看系统状态

```bash
# 查看所有容器状态
docker-compose -f docker-compose.compiled.yml ps

# 查看资源使用
docker stats

# 查看日志
docker-compose -f docker-compose.compiled.yml logs -f --tail=100
```

### 备份数据

```bash
# 导出配置数据
docker exec -it tradingagents-backend-pro python scripts/export_config.py

# 复制备份文件到宿主机
docker cp tradingagents-backend-pro:/app/data/export_*.json ./backup/
```

### 更新系统

```bash
# 拉取最新镜像
docker-compose -f docker-compose.compiled.yml pull

# 重启服务
docker-compose -f docker-compose.compiled.yml up -d
```

### 清理和重置

```bash
# 停止所有服务
docker-compose -f docker-compose.compiled.yml down

# 删除数据卷（⚠️ 会删除所有数据）
docker-compose -f docker-compose.compiled.yml down -v

# 清理未使用的镜像
docker image prune -a
```


---

## 📝 总结

通过本指南，你应该能够：

✅ 在 5 分钟内完成 v2.0 系统部署  
✅ 理解 v2.0 版本的自动初始化特性  
✅ 配置 AI 模型和数据源  
✅ 解决常见部署问题  
✅ 进行系统监控和维护  

**v2.0 版本主要改进**：
- 🚀 **自动初始化**：首次启动自动导入配置和创建用户
- 🔒 **代码保护**：使用编译版镜像，保护核心代码
- ⚡ **性能优化**：Qdrant 向量数据库支持

**下一步**：
1. 探索系统功能，运行第一个股票分析
2. 配置更多 AI 模型，对比分析效果
3. 自定义分析策略和参数
4. 集成到你的投资决策流程

祝你使用愉快！🎉
