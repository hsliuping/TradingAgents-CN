# 🚀 TradingAgents-CN 演示环境快速部署指南

> 使用 Docker Compose 部署完整的 AI 股票分析系统

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

**TradingAgents-CN** 是一个基于多智能体架构的 AI 股票分析系统，支持：

- 🤖 **15+ AI 模型**：集成国内外主流大语言模型
- 📊 **多维度分析**：基本面、技术面、新闻分析、社媒分析
- 🔄 **实时数据**：支持 AKShare、Tushare、BaoStock 等数据源
- 🎨 **现代化界面**：Vue 3 + Element Plus 前端
- 🐳 **容器化部署**：Docker + Docker Compose 一键部署

---

## 🏗️ 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Nginx (端口 80)                           │
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
│  端口: 3000      │                  │  端口: 8000      │
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
- 用户只需访问 `http://服务器IP` 即可使用完整系统
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
│          ⚠️ macOS ARM 用户注意：必须下载 docker-compose.hub.nginx.arm.yml
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

第五阶段：初始化数据（首次部署必做）
└─ 步骤 13：导入初始配置和创建管理员账号 ✓
           ⚠️ 这是必须步骤，否则无法登录系统

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
| **第二阶段：下载部署文件** | | | | |
| 4 | 创建项目目录 | 创建存放配置文件的目录 | ✅ 必须 | 10 秒 |
| 5 | 下载 Compose 文件 | 定义所有服务的配置（前端/后端/数据库/Nginx） | ✅ 必须 | 10 秒 |
| 6 | 下载 .env 文件 | 环境变量配置模板（API 密钥、数据源等） | ✅ 必须 | 10 秒 |
| 7 | 下载 Nginx 配置 | 反向代理配置，统一访问入口 | ✅ 必须 | 10 秒 |
| **第三阶段：配置系统** | | | | |
| 8 | 配置 API 密钥 | 配置 LLM 模型的 API 密钥（如阿里百炼、DeepSeek） | ✅ 必须 | 2-5 分钟 |
| 9 | 配置数据源 | 配置股票数据源（Tushare Token 或使用 AKShare） | ⚠️ 可选 | 2 分钟 |
| **第四阶段：启动服务** | | | | |
| 10 | 拉取镜像 | 从 Docker Hub 下载所有服务的镜像 | ✅ 必须 | 2-5 分钟 |
| 11 | 启动容器 | 启动所有服务（前端/后端/MongoDB/Redis/Nginx） | ✅ 必须 | 30-60 秒 |
| 12 | 检查状态 | 确认所有容器正常运行 | ✅ 必须 | 10 秒 |
| **第五阶段：初始化数据** | | | | |
| 13 | 导入初始配置 | 导入系统配置、LLM 模型列表、创建管理员账号 | ✅ 必须（首次） | 30 秒 |
| **第六阶段：访问系统** | | | | |
| 14 | 浏览器访问 | 打开浏览器访问系统并登录 | ✅ 必须 | 1 分钟 |

### ⚠️ 最容易遗漏的步骤

**请特别注意以下步骤，这些是用户最容易遗漏的：**

#### 1. ❌ 忘记配置 API 密钥（步骤 8）

**后果**：系统可以启动，但无法使用 AI 分析功能，会提示 "API 密钥未配置"

**解决**：
- 必须至少配置一个 LLM 的 API 密钥
- 推荐配置：阿里百炼（国内速度快）或 DeepSeek（性价比高）
- 配置位置：编辑 `.env` 文件中的 `DASHSCOPE_API_KEY` 或 `DEEPSEEK_API_KEY`

#### 2. ❌ 忘记导入初始配置（步骤 13）

**后果**：无法登录系统，没有管理员账号，数据库为空

**解决**：
```bash
# 必须执行此命令
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py
```

#### 3. ❌ macOS ARM 用户使用错误的配置文件（步骤 5）

**后果**：性能极差或无法运行，容器频繁崩溃

**解决**：
- **macOS Apple Silicon (M1/M2/M3)**：必须使用 `docker-compose.hub.nginx.arm.yml`
- **Windows/Linux/macOS Intel**：使用 `docker-compose.hub.nginx.yml`
- 检查方法：在终端运行 `uname -m`，输出 `arm64` 表示 ARM 架构

#### 4. ❌ 没有验证 Docker 安装（步骤 3）

**后果**：后续所有步骤全部失败

**解决**：
```bash
# 运行以下命令验证
docker --version
docker compose version
docker ps
```

### 📞 遇到问题？

如果部署过程中遇到问题，请：

1. 先查看本文档的 [常见问题](#常见问题) 章节
2. 检查 Docker 容器日志：`docker logs tradingagents-backend`
3. 确认是否遗漏了上述关键步骤
4. 添加QQ群 935349777 与我们联系

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

**⚠️ 重要提示**：
- **macOS Apple Silicon (M1/M2/M3) 用户**：必须使用 `docker-compose.hub.nginx.arm.yml` 文件
- **Windows/Linux/macOS Intel 用户**：使用 `docker-compose.hub.nginx.yml` 文件

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

##  Docker 安装指南

如果您尚未安装 Docker 和 Docker Compose，请按照以下步骤安装：

### Windows 用户

#### 方法 1：使用 Hyper-V 模式（推荐，更简单）

**适用于**：Windows 10 Pro/Enterprise/Education 或 Windows 11

**优点**：无需安装 WSL 2，配置简单，性能稳定

1. **启用 Hyper-V**
   ```powershell
   # 方法 1：通过 Windows 功能启用
   # 1. 打开"控制面板"
   # 2. 点击"程序" → "启用或关闭 Windows 功能"
   # 3. 勾选"Hyper-V"（包括所有子项）
   # 4. 点击"确定"并重启计算机

   # 方法 2：通过 PowerShell 启用（管理员权限）
   Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All

   # 重启计算机
   ```

2. **检查虚拟化是否启用**
   ```powershell
   # 打开任务管理器 → 性能 → CPU
   # 查看"虚拟化"是否显示"已启用"
   # 如果显示"已禁用"，需要在 BIOS 中启用 VT-x/AMD-V
   ```

3. **下载并安装 Docker Desktop**
   - 访问 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
   - 点击 "Download for Windows" 下载安装包
   - 双击 `Docker Desktop Installer.exe` 运行安装程序
   - **重要**：安装时**取消勾选** "Use WSL 2 instead of Hyper-V"（使用 Hyper-V 模式）
   - 按照安装向导完成安装

4. **启动 Docker Desktop**
   - 从开始菜单启动 Docker Desktop
   - 首次启动时，选择 "Use Hyper-V backend"
   - 等待 Docker 引擎启动（任务栏图标变为绿色）

5. **验证安装**
   ```powershell
   # 打开 PowerShell，运行：
   docker --version
   docker compose version

   # 预期输出：
   # Docker version 24.0.x, build xxxxx
   # Docker Compose version v2.x.x

   # 测试运行容器
   docker run hello-world
   ```

---

#### 方法 2：使用 WSL 2 模式（适合开发者）

**适用于**：Windows 10 Home/Pro/Enterprise 或 Windows 11

**优点**：更好的性能，与 Linux 环境集成

**缺点**：需要额外安装 WSL 2，配置相对复杂

1. **启用 WSL 2**
   ```powershell
   # 以管理员身份打开 PowerShell，运行：
   wsl --install

   # 重启计算机
   ```

2. **验证 WSL 2 安装**
   ```powershell
   # 检查 WSL 版本
   wsl --list --verbose

   # 如果提示 "WSL 2 installation is incomplete"，手动安装内核更新包
   # 下载地址：https://aka.ms/wsl2kernel
   ```

3. **下载并安装 Docker Desktop**
   - 访问 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
   - 点击 "Download for Windows" 下载安装包
   - 双击 `Docker Desktop Installer.exe` 运行安装程序
   - **勾选** "Use WSL 2 instead of Hyper-V"（使用 WSL 2 模式）
   - 按照安装向导完成安装

4. **启动 Docker Desktop**
   - 从开始菜单启动 Docker Desktop
   - 等待 Docker 引擎启动（任务栏图标变为绿色）

5. **验证安装**
   ```powershell
   # 打开 PowerShell，运行：
   docker --version
   docker compose version

   # 预期输出：
   # Docker version 24.0.x, build xxxxx
   # Docker Compose version v2.x.x
   ```

---

#### 常见问题

**问题 1**：不知道选择 Hyper-V 还是 WSL 2？

| 特性 | Hyper-V 模式 | WSL 2 模式 |
|------|-------------|-----------|
| **适用版本** | Windows 10 Pro/Enterprise/Education, Windows 11 | Windows 10 Home/Pro/Enterprise, Windows 11 |
| **配置难度** | ⭐⭐ 简单 | ⭐⭐⭐ 中等 |
| **性能** | ⭐⭐⭐⭐ 稳定 | ⭐⭐⭐⭐⭐ 更快 |
| **Linux 集成** | ❌ 无 | ✅ 完整支持 |
| **推荐场景** | 仅运行 Docker 容器 | 需要 Linux 开发环境 |

**推荐**：如果只是运行 TradingAgents-CN，选择 **Hyper-V 模式**更简单！

**问题 2**：Docker Desktop 无法启动

```powershell
# 检查 1：确认虚拟化已启用
# 任务管理器 → 性能 → CPU → 虚拟化应显示"已启用"
# 如果未启用，需要在 BIOS 中启用 VT-x（Intel）或 AMD-V（AMD）

# 检查 2：确认 Hyper-V 已启用（如果使用 Hyper-V 模式）
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V

# 检查 3：查看 Docker Desktop 日志
# Docker Desktop → Settings → Troubleshoot → Show logs
```

**问题 3**：提示 "Hardware assisted virtualization and data execution protection must be enabled in the BIOS"

```
解决方案：在 BIOS 中启用虚拟化
1. 重启计算机，进入 BIOS 设置（通常按 F2、F10、Del 键）
2. 找到虚拟化选项：
   - Intel CPU：Intel VT-x 或 Intel Virtualization Technology
   - AMD CPU：AMD-V 或 SVM Mode
3. 启用虚拟化选项
4. 保存并退出 BIOS
```

**问题 4**：Windows 10 Home 版本无法使用 Hyper-V

```
解决方案：使用 WSL 2 模式
- Windows 10 Home 不支持 Hyper-V
- 必须使用 WSL 2 模式（参考上方"方法 2"）
- 或者升级到 Windows 10 Pro/Enterprise
```

---

### Linux 用户

#### Ubuntu / Debian

```bash
# 1. 更新软件包索引
sudo apt-get update

# 2. 安装必要的依赖
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# 3. 添加 Docker 官方 GPG 密钥
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 4. 设置 Docker 仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 5. 安装 Docker Engine 和 Docker Compose
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 6. 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 7. 将当前用户添加到 docker 组（避免每次使用 sudo）
sudo usermod -aG docker $USER

# 8. 重新登录或运行以下命令使组权限生效
newgrp docker

# 9. 验证安装
docker --version
docker compose version
```

#### CentOS / RHEL

```bash
# 1. 卸载旧版本（如果存在）
sudo yum remove docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine

# 2. 安装必要的依赖
sudo yum install -y yum-utils

# 3. 设置 Docker 仓库
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 4. 安装 Docker Engine 和 Docker Compose
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 6. 将当前用户添加到 docker 组
sudo usermod -aG docker $USER

# 7. 重新登录或运行以下命令使组权限生效
newgrp docker

# 8. 验证安装
docker --version
docker compose version
```

**常见问题**：

- **问题 1**：提示 "permission denied"
  ```bash
  # 解决方案：确保已将用户添加到 docker 组并重新登录
  sudo usermod -aG docker $USER
  newgrp docker
  ```

- **问题 2**：Docker 服务无法启动
  ```bash
  # 检查服务状态
  sudo systemctl status docker

  # 查看日志
  sudo journalctl -u docker.service
  ```

---

### macOS 用户

#### 安装 Docker Desktop（推荐）

1. **下载 Docker Desktop**
   - 访问 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
   - **Apple Silicon (M1/M2/M3)**：选择 "Mac with Apple chip"
   - **Intel 芯片**：选择 "Mac with Intel chip"

2. **安装 Docker Desktop**
   - 双击下载的 `Docker.dmg` 文件
   - 将 Docker 图标拖到 Applications 文件夹
   - 从 Applications 文件夹启动 Docker
   - 按照提示完成初始设置

3. **验证安装**
   ```bash
   # 打开终端，运行：
   docker --version
   docker compose version

   # 预期输出：
   # Docker version 24.0.x, build xxxxx
   # Docker Compose version v2.x.x
   ```

**常见问题**：

- **问题 1**：提示 "Docker Desktop requires macOS 10.15 or later"
  ```
  解决方案：升级 macOS 到最新版本
  - 系统偏好设置 → 软件更新
  ```

- **问题 2**：Apple Silicon Mac 性能问题
  ```bash
  # 解决方案：确保使用 ARM 版本的 Docker Desktop 和镜像
  # 检查架构：
  uname -m
  # 输出 "arm64" 表示 Apple Silicon
  # 输出 "x86_64" 表示 Intel
  ```

---

### Docker Compose 命令说明

Docker Desktop 自带 Docker Compose V2，有两种使用方式：

#### 新版命令（推荐）

```bash
docker compose version    # 查看版本
docker compose up -d      # 启动服务
docker compose down       # 停止服务
docker compose ps         # 查看服务状态
docker compose logs       # 查看日志
```

#### 旧版命令（兼容）

```bash
docker-compose version    # 查看版本
docker-compose up -d      # 启动服务
docker-compose down       # 停止服务
docker-compose ps         # 查看服务状态
docker-compose logs       # 查看日志
```

**说明**：
- 新版使用 `docker compose`（空格），旧版使用 `docker-compose`（连字符）
- 两种方式功能相同，本文档使用旧版命令以保持兼容性
- 如果提示 "docker-compose: command not found"，请使用新版命令 `docker compose`

---

## 快速开始

### 一键部署（5 分钟）

#### Windows 用户（推荐）

**第一步：打开 PowerShell 窗口**

有以下几种方式打开 PowerShell：

**方法 1：通过开始菜单（推荐）**
```
1. 点击 Windows 开始菜单
2. 输入 "PowerShell"
3. 右键点击 "Windows PowerShell"
4. 选择 "以管理员身份运行"（推荐）或直接点击打开
```

**方法 2：通过右键菜单（快捷）**
```
1. 按住 Shift 键
2. 在桌面或任意文件夹空白处右键点击
3. 选择 "在此处打开 PowerShell 窗口"
```

**方法 3：通过运行命令（快速）**
```
1. 按 Win + R 键
2. 输入 "powershell"
3. 按 Enter 键
```

**方法 4：通过 Windows Terminal（Windows 11 推荐）**
```
1. 点击 Windows 开始菜单
2. 输入 "Terminal" 或 "终端"
3. 点击 "Windows Terminal" 打开
4. 默认会打开 PowerShell 标签页
```

**💡 提示**：
- 如果执行命令时提示权限不足，请以管理员身份运行 PowerShell
- Windows 11 用户推荐使用 Windows Terminal，体验更好

---

**第二步：执行部署命令**

```powershell
# 1. 创建项目目录
New-Item -ItemType Directory -Path "$env:USERPROFILE\tradingagents-demo" -Force
Set-Location "$env:USERPROFILE\tradingagents-demo"

# 2. 下载部署文件
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/docker-compose.hub.nginx.yml" -OutFile "docker-compose.hub.nginx.yml"

# 3. 下载环境配置文件
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/.env.docker" -OutFile ".env"

# 4. 配置 API 密钥（⚠️ 重要：必须配置，否则无法使用 AI 分析功能）
notepad .env
# 或使用 VS Code 编辑：code .env

# ⚠️ 请在打开的编辑器中配置以下内容（至少配置一个）：
#
# 阿里百炼（推荐，国内速度快）：
#   找到 DASHSCOPE_API_KEY= 这一行
#   将等号后面改为你的 API Key，例如：DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxx
#
# DeepSeek（推荐，性价比高）：
#   找到 DEEPSEEK_API_KEY= 这一行
#   将等号后面改为你的 API Key，例如：DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
#
# 其他可选配置：
#   - TUSHARE_TOKEN=你的Tushare Token（可选，用于获取更全面的股票数据，注册地址：https://tushare.pro/weborder/#/login?reg=tacn）
#   - OPENAI_API_KEY=你的OpenAI Key（可选）
#
# 配置完成后保存并关闭编辑器

# 5. 下载 Nginx 配置文件
New-Item -ItemType Directory -Path "nginx" -Force
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/nginx/nginx.conf" -OutFile "nginx\nginx.conf"

# 6. 拉取 Docker 镜像（首次部署需要下载，需要 2-5 分钟）
docker-compose -f docker-compose.hub.nginx.yml pull

# 7. 启动所有服务
docker-compose -f docker-compose.hub.nginx.yml up -d

# 8. 检查服务状态（等待所有服务变为 healthy，约 30-60 秒）
docker-compose -f docker-compose.hub.nginx.yml ps

# 9. 导入初始配置（⚠️ 重要：首次部署必须执行，否则无法登录）
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py

# 10. 访问系统
# 浏览器打开: http://localhost 或 http://你的服务器IP
# 默认账号: admin / admin123
# ⚠️ 登录后请立即修改默认密码！
```

#### Linux 用户

```bash
# 1. 创建项目目录
mkdir -p ~/tradingagents-demo
cd ~/tradingagents-demo

# 2. 下载部署文件
wget https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/docker-compose.hub.nginx.yml

# 3. 下载环境配置文件
wget https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/.env.docker -O .env

# 4. 配置 API 密钥（⚠️ 重要：必须配置，否则无法使用 AI 分析功能）
nano .env
# 或使用 vim 编辑：vim .env

# ⚠️ 请在打开的编辑器中配置以下内容（至少配置一个）：
#
# 阿里百炼（推荐，国内速度快）：
#   找到 DASHSCOPE_API_KEY= 这一行
#   将等号后面改为你的 API Key，例如：DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxx
#
# DeepSeek（推荐，性价比高）：
#   找到 DEEPSEEK_API_KEY= 这一行
#   将等号后面改为你的 API Key，例如：DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
#
# 其他可选配置：
#   - TUSHARE_TOKEN=你的Tushare Token（可选，用于获取更全面的股票数据，注册地址：https://tushare.pro/weborder/#/login?reg=tacn）
#   - OPENAI_API_KEY=你的OpenAI Key（可选）
#
# 配置完成后保存并退出编辑器（nano: Ctrl+X, Y, Enter；vim: :wq）

# 5. 下载 Nginx 配置文件
mkdir -p nginx
wget https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/nginx/nginx.conf -O nginx/nginx.conf

# 6. 拉取 Docker 镜像（首次部署需要下载，需要 2-5 分钟）
docker-compose -f docker-compose.hub.nginx.yml pull

# 7. 启动所有服务
docker-compose -f docker-compose.hub.nginx.yml up -d

# 8. 检查服务状态（等待所有服务变为 healthy，约 30-60 秒）
docker-compose -f docker-compose.hub.nginx.yml ps

# 9. 导入初始配置（⚠️ 重要：首次部署必须执行，否则无法登录）
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py

# 10. 访问系统
# 浏览器打开: http://localhost 或 http://你的服务器IP
# 默认账号: admin / admin123
# ⚠️ 登录后请立即修改默认密码！
```

#### macOS 用户（Apple Silicon M1/M2/M3）

```bash
# 1. 创建项目目录
mkdir -p ~/tradingagents-demo
cd ~/tradingagents-demo

# 2. 下载 ARM 架构部署文件（重要！）
curl -O https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/docker-compose.hub.nginx.arm.yml

# 3. 下载环境配置文件
curl -o .env https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/.env.docker

# 4. 配置 API 密钥（⚠️ 重要：必须配置，否则无法使用 AI 分析功能）
nano .env
# 或使用 vim 编辑：vim .env

# ⚠️ 请在打开的编辑器中配置以下内容（至少配置一个）：
#
# 阿里百炼（推荐，国内速度快）：
#   找到 DASHSCOPE_API_KEY= 这一行
#   将等号后面改为你的 API Key，例如：DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxx
#
# DeepSeek（推荐，性价比高）：
#   找到 DEEPSEEK_API_KEY= 这一行
#   将等号后面改为你的 API Key，例如：DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
#
# 其他可选配置：
#   - TUSHARE_TOKEN=你的Tushare Token（可选，用于获取更全面的股票数据，注册地址：https://tushare.pro/weborder/#/login?reg=tacn）
#   - OPENAI_API_KEY=你的OpenAI Key（可选）
#
# 配置完成后保存并退出编辑器（nano: Ctrl+X, Y, Enter；vim: :wq）

# 5. 下载 Nginx 配置文件
mkdir -p nginx
curl -o nginx/nginx.conf https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/nginx/nginx.conf

# 6. 拉取 Docker 镜像（首次部署需要下载，需要 2-5 分钟）
docker-compose -f docker-compose.hub.nginx.arm.yml pull

# 7. 启动所有服务（使用 ARM 版本）
docker-compose -f docker-compose.hub.nginx.arm.yml up -d

# 8. 检查服务状态（等待所有服务变为 healthy，约 30-60 秒）
docker-compose -f docker-compose.hub.nginx.arm.yml ps

# 9. 导入初始配置（⚠️ 重要：首次部署必须执行，否则无法登录）
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py

# 10. 访问系统
# 浏览器打开: http://localhost
# 默认账号: admin / admin123
# ⚠️ 登录后请立即修改默认密码！
```

**macOS Intel 芯片用户**：使用 Linux 用户的命令即可。

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

**重要提示**：Apple Silicon Mac 必须使用 `docker-compose.hub.nginx.arm.yml` 文件！

### 步骤 2：下载部署文件

创建项目目录并下载必要文件：

#### Windows 用户（PowerShell）

```powershell
# 创建项目目录
New-Item -ItemType Directory -Path "$env:USERPROFILE\tradingagents-demo" -Force
Set-Location "$env:USERPROFILE\tradingagents-demo"

# 下载 Docker Compose 配置文件
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/docker-compose.hub.nginx.yml" -OutFile "docker-compose.hub.nginx.yml"

# 下载环境配置文件
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/.env.docker" -OutFile ".env"

# 创建 Nginx 配置目录并下载配置文件
New-Item -ItemType Directory -Path "nginx" -Force
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/nginx/nginx.conf" -OutFile "nginx\nginx.conf"
```

**提示**：如果遇到 PowerShell 执行策略限制，请以管理员身份运行 PowerShell 并执行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Linux 用户

```bash
# 创建项目目录
mkdir -p ~/tradingagents-demo
cd ~/tradingagents-demo

# 下载 Docker Compose 配置文件
wget https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/docker-compose.hub.nginx.yml

# 下载环境配置文件
wget https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/.env.docker -O .env

# 创建 Nginx 配置目录并下载配置文件
mkdir -p nginx
wget https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/nginx/nginx.conf -O nginx/nginx.conf
```

#### macOS 用户

**Apple Silicon (M1/M2/M3)**：

```bash
# 创建项目目录
mkdir -p ~/tradingagents-demo
cd ~/tradingagents-demo

# 下载 ARM 架构 Docker Compose 配置文件（重要！）
curl -O https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/docker-compose.hub.nginx.arm.yml

# 下载环境配置文件
curl -o .env https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/.env.docker

# 创建 Nginx 配置目录并下载配置文件
mkdir -p nginx
curl -o nginx/nginx.conf https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/v1.0.0-preview/nginx/nginx.conf
```

**Intel 芯片**：使用 Linux 用户的命令即可。

### 步骤 3：配置 API 密钥（重要）

编辑 `.env` 文件，配置至少一个 AI 模型的 API 密钥：

#### Windows 用户

```powershell
# 使用记事本打开
notepad .env

# 或使用 VS Code（如果已安装）
code .env
```

#### Linux 用户

```bash
# 使用文本编辑器打开
nano .env  # 或 vim .env
```

#### macOS 用户

```bash
# 使用文本编辑器打开
nano .env  # 或 vim .env

# 或使用 VS Code（如果已安装）
code .env
```

**必需配置**（至少配置一个）：

```bash
# 阿里百炼（推荐，国产模型，中文优化）
DASHSCOPE_API_KEY=sk-your-dashscope-api-key-here

# 或 DeepSeek（推荐，性价比高）
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
DEEPSEEK_ENABLED=true

# 或 OpenAI（需要国外网络）
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_ENABLED=true
```

**可选配置**：

```bash
# Tushare 数据源（专业金融数据，需要注册）
TUSHARE_TOKEN=your-tushare-token-here
TUSHARE_ENABLED=true

# 其他 AI 模型
QIANFAN_API_KEY=your-qianfan-api-key-here  # 百度文心一言
GOOGLE_API_KEY=your-google-api-key-here    # Google Gemini
```

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
docker-compose -f docker-compose.hub.nginx.yml pull

# 启动所有服务（后台运行）
docker-compose -f docker-compose.hub.nginx.yml up -d

# 查看服务状态
docker-compose -f docker-compose.hub.nginx.yml ps
```

#### Linux 用户

```bash
# 拉取最新镜像
docker-compose -f docker-compose.hub.nginx.yml pull

# 启动所有服务（后台运行）
docker-compose -f docker-compose.hub.nginx.yml up -d

# 查看服务状态
docker-compose -f docker-compose.hub.nginx.yml ps
```

#### macOS 用户

**Apple Silicon (M1/M2/M3)**：

```bash
# 拉取最新镜像（ARM 版本）
docker-compose -f docker-compose.hub.nginx.arm.yml pull

# 启动所有服务（后台运行）
docker-compose -f docker-compose.hub.nginx.arm.yml up -d

# 查看服务状态
docker-compose -f docker-compose.hub.nginx.arm.yml ps
```

**Intel 芯片**：使用 Linux 用户的命令即可。

**预期输出**：

```
NAME                       IMAGE                                    STATUS
tradingagents-backend      hsliup/tradingagents-backend:latest      Up (healthy)
tradingagents-frontend     hsliup/tradingagents-frontend:latest     Up (healthy)
tradingagents-mongodb      mongo:4.4                                Up (healthy)
tradingagents-nginx        nginx:alpine                             Up
tradingagents-redis        redis:7-alpine                           Up (healthy)
```

**Windows 用户注意事项**：
- 如果遇到 "docker-compose: command not found"，请使用 `docker compose`（不带连字符）
- 确保 Docker Desktop 已启动并运行
- 如果遇到端口占用（80 端口），请检查是否有其他程序占用该端口（如 IIS、Apache）

### 步骤 5：导入初始配置

**首次部署必须执行此步骤**，导入系统配置和创建管理员账号：

#### Windows 用户（PowerShell）

```powershell
# 导入配置数据（包含 15+ 个预配置的 LLM 模型和示例数据）
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py
```

#### Linux 用户

```bash
# 导入配置数据（包含 15+ 个预配置的 LLM 模型和示例数据）
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py
```

#### macOS 用户

```bash
# 导入配置数据（包含 15+ 个预配置的 LLM 模型和示例数据）
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py
```

**注意**：无论使用哪个 docker-compose 文件启动，容器名称都是相同的，所以导入命令一致。

**预期输出**：

```
================================================================================
📦 导入配置数据并创建默认用户
================================================================================

✅ MongoDB 连接成功
✅ 文件加载成功
   导出时间: 2025-10-17T05:50:07
   集合数量: 11

🚀 开始导入...
   ✅ 插入 79 个系统配置
   ✅ 插入 8 个 LLM 提供商

👤 创建默认管理员用户...
   ✅ 用户创建成功

🔐 登录信息:
   用户名: admin
   密码: admin123
```

**说明**：
- 此脚本会自动创建系统所需的配置数据和管理员账号
- 如果已经导入过，脚本会跳过已存在的数据
- 无需手动下载配置文件，所有配置都内置在 Docker 镜像中

### 步骤 6：访问系统

打开浏览器，访问：

#### Windows 本地部署

```
http://localhost
```

#### 服务器部署

```
http://你的服务器IP
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
- 如果无法访问 `http://localhost`，请检查 Docker Desktop 是否正常运行
- 如果提示端口占用，请检查 80 端口是否被其他程序占用（如 IIS）
- 可以使用 `netstat -ano | findstr :80` 查看端口占用情况

---

## ⚙️ 配置说明

### 目录结构

#### Windows 用户

```
C:\Users\你的用户名\tradingagents-demo\
├── docker-compose.hub.nginx.yml  # Docker Compose 配置文件
├── .env                          # 环境变量配置
├── nginx\
│   └── nginx.conf                # Nginx 配置文件
├── logs\                         # 日志目录（自动创建）
├── data\                         # 数据目录（自动创建）
└── config\                       # 配置目录（自动创建）
```

#### Linux 用户

```
~/tradingagents-demo/
├── docker-compose.hub.nginx.yml  # Docker Compose 配置文件
├── .env                          # 环境变量配置
├── nginx/
│   └── nginx.conf                # Nginx 配置文件
├── logs/                         # 日志目录（自动创建）
├── data/                         # 数据目录（自动创建）
└── config/                       # 配置目录（自动创建）
```

#### macOS 用户

**Apple Silicon (M1/M2/M3)**：

```
~/tradingagents-demo/
├── docker-compose.hub.nginx.arm.yml  # ARM 架构 Docker Compose 配置文件
├── .env                              # 环境变量配置
├── nginx/
│   └── nginx.conf                    # Nginx 配置文件
├── logs/                             # 日志目录（自动创建）
├── data/                             # 数据目录（自动创建）
└── config/                           # 配置目录（自动创建）
```

**Intel 芯片**：与 Linux 用户目录结构相同。

**说明**：
- 初始配置数据已内置在 Docker 镜像中，无需手动下载
- `logs/`、`data/`、`config/` 目录会在首次启动时自动创建

### 端口说明

| 服务 | 容器内端口 | 宿主机端口 | 说明 |
|------|-----------|-----------|------|
| Nginx | 80 | 80 | 统一入口，处理前端和 API |
| Backend | 8000 | - | 内部端口，通过 Nginx 访问 |
| Frontend | 80 | - | 内部端口，通过 Nginx 访问 |
| MongoDB | 27017 | 27017 | 数据库（可选暴露） |
| Redis | 6379 | 6379 | 缓存（可选暴露） |

### 数据持久化

系统使用 Docker Volume 持久化数据：

#### Windows 用户

```powershell
# 查看数据卷
docker volume ls | Select-String tradingagents

# 备份数据卷
docker run --rm -v tradingagents_mongodb_data:/data -v ${PWD}:/backup alpine tar czf /backup/mongodb_backup.tar.gz /data

# 恢复数据卷
docker run --rm -v tradingagents_mongodb_data:/data -v ${PWD}:/backup alpine tar xzf /backup/mongodb_backup.tar.gz -C /
```

#### Linux 用户

```bash
# 查看数据卷
docker volume ls | grep tradingagents

# 备份数据卷
docker run --rm -v tradingagents_mongodb_data:/data -v $(pwd):/backup alpine tar czf /backup/mongodb_backup.tar.gz /data

# 恢复数据卷
docker run --rm -v tradingagents_mongodb_data:/data -v $(pwd):/backup alpine tar xzf /backup/mongodb_backup.tar.gz -C /
```

#### macOS 用户

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
docker-compose -f docker-compose.hub.nginx.yml logs

# 查看特定服务日志
docker-compose -f docker-compose.hub.nginx.yml logs backend

# 重启服务
docker-compose -f docker-compose.hub.nginx.yml restart
```

### 2. 无法访问系统

**问题**：浏览器无法打开 `http://localhost` 或 `http://服务器IP`

#### Windows 用户检查清单

```powershell
# 1. 检查服务状态
docker-compose -f docker-compose.hub.nginx.yml ps

# 2. 检查端口占用
netstat -ano | findstr :80

# 3. 检查 Docker Desktop 是否运行
# 打开 Docker Desktop 应用，确保状态为 "Running"

# 4. 如果 80 端口被占用，停止占用程序
# 常见占用程序：IIS、Apache、Skype
# 停止 IIS：
Stop-Service -Name W3SVC

# 或修改 docker-compose.hub.nginx.yml 使用其他端口（如 8080）
# 将 "80:80" 改为 "8080:80"，然后访问 http://localhost:8080
```

#### Linux 用户检查清单

```bash
# 1. 检查服务状态
docker-compose -f docker-compose.hub.nginx.yml ps

# 2. 检查端口占用
sudo netstat -tulpn | grep :80

# 3. 检查防火墙
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS

# 4. 开放 80 端口
sudo ufw allow 80  # Ubuntu
sudo firewall-cmd --add-port=80/tcp --permanent && sudo firewall-cmd --reload  # CentOS
```

#### macOS 用户检查清单

**Apple Silicon (M1/M2/M3)**：

```bash
# 1. 检查服务状态
docker-compose -f docker-compose.hub.nginx.arm.yml ps

# 2. 检查端口占用
lsof -i :80

# 3. 检查 Docker Desktop 是否运行
# 打开 Docker Desktop 应用，确保状态为 "Running"

# 4. 如果 80 端口被占用，修改端口
# 编辑 docker-compose.hub.nginx.arm.yml
# 将 "80:80" 改为 "8080:80"，然后访问 http://localhost:8080
```

**Intel 芯片**：使用 Linux 用户的命令（将 `docker-compose.hub.nginx.yml` 替换为实际使用的文件）。

### 3. API 请求失败

**问题**：前端显示"网络错误"或"API 请求失败"

#### Windows 用户解决方案

```powershell
# 检查后端日志
docker logs tradingagents-backend

# 检查 Nginx 日志
docker logs tradingagents-nginx

# 测试后端健康检查（使用 PowerShell）
Invoke-WebRequest -Uri "http://localhost:8000/api/health"

# 或使用 curl（如果已安装）
curl http://localhost:8000/api/health
```

#### Linux 用户解决方案

```bash
# 检查后端日志
docker logs tradingagents-backend

# 检查 Nginx 日志
docker logs tradingagents-nginx

# 测试后端健康检查
curl http://localhost:8000/api/health
```

#### macOS 用户解决方案

```bash
# 检查后端日志
docker logs tradingagents-backend

# 检查 Nginx 日志
docker logs tradingagents-nginx

# 测试后端健康检查
curl http://localhost:8000/api/health
```

### 4. 数据库连接失败

**问题**：后端日志显示"MongoDB connection failed"

**解决方案**：

```bash
# 检查 MongoDB 状态
docker exec -it tradingagents-mongodb mongo -u admin -p tradingagents123 --authenticationDatabase admin

# 重启 MongoDB
docker-compose -f docker-compose.hub.nginx.yml restart mongodb

# 检查数据卷
docker volume inspect tradingagents_mongodb_data
```

### 5. 内存不足

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

# 限制容器内存（编辑 docker-compose.hub.nginx.yml）
# 使用记事本或 VS Code 打开文件，添加：
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

#### Linux 用户解决方案

```bash
# 查看资源使用情况
docker stats

# 清理未使用的资源
docker system prune -a

# 限制容器内存（编辑 docker-compose.hub.nginx.yml）
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

#### macOS 用户解决方案

```bash
# 查看资源使用情况
docker stats

# 清理未使用的资源
docker system prune -a

# 调整 Docker Desktop 内存限制
# 1. 打开 Docker Desktop
# 2. 点击 Settings → Resources
# 3. 调整 Memory 滑块（推荐至少 4GB）
# 4. 点击 Apply & Restart

# 限制容器内存（编辑对应的 docker-compose 文件）
# Apple Silicon: 编辑 docker-compose.hub.nginx.arm.yml
# Intel: 编辑 docker-compose.hub.nginx.yml
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

编辑 `nginx/nginx.conf`：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 修改为你的域名
    
    # ... 其他配置保持不变
}
```

配置 DNS 解析，将域名指向服务器 IP，然后重启 Nginx：

```bash
docker-compose -f docker-compose.hub.nginx.yml restart nginx
```

### 启用 HTTPS

1. 获取 SSL 证书（推荐使用 Let's Encrypt）：

```bash
# 安装 certbot
sudo apt install certbot

# 获取证书
sudo certbot certonly --standalone -d your-domain.com
```

2. 修改 `nginx/nginx.conf`：

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
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

3. 挂载证书目录并重启：

```yaml
# docker-compose.hub.nginx.yml
services:
  nginx:
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

### 性能优化

#### 1. 启用 Redis 持久化

编辑 `docker-compose.hub.nginx.yml`：

```yaml
services:
  redis:
    command: redis-server --appendonly yes --requirepass tradingagents123 --maxmemory 2gb --maxmemory-policy allkeys-lru
```

#### 2. MongoDB 索引优化

```bash
# 进入 MongoDB
docker exec -it tradingagents-mongodb mongo -u admin -p tradingagents123 --authenticationDatabase admin

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
/path/to/tradingagents-demo/logs/*.log {
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
docker-compose -f docker-compose.hub.nginx.yml ps

# 查看资源使用
docker stats

# 查看日志
docker-compose -f docker-compose.hub.nginx.yml logs -f --tail=100
```

### 备份数据

```bash
# 导出配置数据
docker exec -it tradingagents-backend python -c "
from app.services.database.backups import export_data
import asyncio
asyncio.run(export_data(
    collections=['system_configs', 'users', 'llm_providers', 'market_quotes', 'stock_basic_info'],
    export_dir='/app/data',
    format='json'
))
"

# 复制备份文件到宿主机
docker cp tradingagents-backend:/app/data/export_*.json ./backup/
```

### 更新系统

```bash
# 拉取最新镜像
docker-compose -f docker-compose.hub.nginx.yml pull

# 重启服务
docker-compose -f docker-compose.hub.nginx.yml up -d
```

### 清理和重置

```bash
# 停止所有服务
docker-compose -f docker-compose.hub.nginx.yml down

# 删除数据卷（⚠️ 会删除所有数据）
docker-compose -f docker-compose.hub.nginx.yml down -v

# 清理未使用的镜像
docker image prune -a
```

---

## 🆘 获取帮助

- **GitHub Issues**: https://github.com/hsliuping/TradingAgents-CN/issues
- **文档**: https://github.com/hsliuping/TradingAgents-CN/tree/v1.0.0-preview/docs
- **示例**: https://github.com/hsliuping/TradingAgents-CN/tree/v1.0.0-preview/examples

---

## 📝 总结

通过本指南，你应该能够：

✅ 在 5 分钟内完成系统部署  
✅ 理解系统架构和组件关系  
✅ 配置 AI 模型和数据源  
✅ 解决常见部署问题  
✅ 进行系统监控和维护  

**下一步**：
1. 探索系统功能，运行第一个股票分析
2. 配置更多 AI 模型，对比分析效果
3. 自定义分析策略和参数
4. 集成到你的投资决策流程

祝你使用愉快！🎉

