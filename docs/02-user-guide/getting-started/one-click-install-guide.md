# 一键安装使用手册（社区版）

社区版提供一键安装脚本，无需 Docker、无需手工配置数据库，下载一个脚本即可完成全部部署：

1. Python 环境准备（缺失时自动安装）
2. 获取代码
3. 下载 MongoDB / Redis 运行时（本地目录，不污染系统）
4. 构建前端
5. 创建虚拟环境并安装依赖
6. 生成 `.env`（随机密钥 + 管理员密码）
7. 启动 MongoDB / Redis / Web 服务

安装完成后只需一个地址即可使用：**http://127.0.0.1:8000**

## 1. 系统支持

| 系统 | 要求 |
|------|------|
| Windows | 10 / 11（自带 PowerShell；需 Python 3.11+ 或 winget） |
| macOS | 12+（Intel / Apple Silicon；需 Homebrew，或已有 Python 3.11+） |
| Linux | Ubuntu 20.04+ / Debian 11+，或 Rocky Linux、AlmaLinux、CentOS Stream、RHEL 8 / 9 |

> **CentOS 7 不支持**：系统 glibc（2.17）过旧，MongoDB 7 / Node 20 均要求 glibc 2.28+。
> 请升级到 Rocky Linux / AlmaLinux / CentOS Stream 8-9，或改用 Docker 部署。

脚本会自动检测发行版：Debian 系走 `apt`，RHEL 系走 `dnf`，并自动下载对应平台的 MongoDB 预编译包。

## 2. 快速开始

### Windows

```powershell
# 下载脚本后执行（无需管理员权限）
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

### macOS / Linux

```bash
chmod +x install.sh
./install.sh
```

安装目录默认为 `~/TradingAgentsCN`（Windows 为 `%USERPROFILE%\TradingAgentsCN`）。

## 3. 首次登录

安装结束时会在终端打印：

```
==================================================
 TradingAgents-CN 安装完成
==================================================
  访问地址   : http://127.0.0.1:8000
  管理员账号 : admin
  管理员密码 : admin3f9a2c1b
  项目目录   : /home/you/TradingAgentsCN
  日志目录   : /home/you/TradingAgentsCN/logs
  启动/停止  : ./start.sh / ./stop.sh
==================================================
```

用浏览器打开访问地址，使用 `admin` 与打印的密码登录。**请妥善保存该密码**——它同时写入项目目录的 `.env`（`ADMIN_DEFAULT_PASSWORD`），丢失后可在 `.env` 中修改、重启服务生效。

## 4. 常用参数

两个脚本参数一致（Windows 用 `-` 前缀，Linux/macOS 用 `--` 前缀）：

| 功能 | Linux / macOS | Windows |
|------|---------------|----------|
| 自定义 Web 端口 | `--port 8080` | `-Port 8080` |
| 自定义 MongoDB 端口 | `--mongo-port 27018` | `-MongoPort 27018` |
| 自定义 Redis 端口 | `--redis-port 6380` | `-RedisPort 6380` |
| 指定管理员密码 | `--admin-password MyPass123!` | `-AdminPassword MyPass123!` |
| 指定安装目录 | `--install-dir /opt/tacn` | `-InstallDir D:\tacn` |
| 下载镜像加速 | `--mirror https://your-mirror` | `-Mirror https://your-mirror` |
| 只安装不启动 | `--no-start` | `-NoStart` |
| 跳过前端构建（已有 dist） | `--skip-frontend-build` | `-SkipFrontendBuild` |
| 查看帮助 | `./install.sh --help` | `Get-Help .\install.ps1` |

示例（自定义端口 + 固定密码）：

```bash
./install.sh --port 8080 --admin-password MyPass123!
```

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Port 8080 -AdminPassword "MyPass123!"
```

## 5. 安装目录结构

```
TradingAgentsCN/
├── install.sh / install.ps1      # 安装脚本（可重复执行，幂等）
├── start.sh / start.ps1          # 日常启动（安装时自动生成）
├── stop.sh / stop.ps1            # 日常停止（安装时自动生成）
├── .env                          # 配置与密钥（勿外传）
├── .venv/                        # Python 虚拟环境
├── runtime/                      # MongoDB / Redis / Node 运行时
├── data/mongodb/ data/redis/     # 数据库数据（备份 = 备份这两个目录）
└── logs/                         # 各服务日志
    ├── server.out.log / server.err.log
    ├── mongod.out.log / mongod.err.log
    └── redis.out.log / redis.err.log
```

## 6. 日常启停

**Linux / macOS**（安装时自动生成）：

```bash
./start.sh     # 启动 Web 服务
./stop.sh      # 停止 Web / MongoDB / Redis
```

**Windows**：

```powershell
.\start.ps1
.\stop.ps1
```

手动启动（任何平台，需在项目目录执行）：

```bash
# Linux / macOS
.venv/bin/python installer/run_server.py

# Windows
.venv\Scripts\python installer\run_server.py
```

> MongoDB / Redis 由安装脚本启动后常驻后台；`start.sh` 只负责（重新）启动 Web 服务，`stop.sh` 按 pid 依次停止 Web / MongoDB / Redis 三个服务。单独重启数据库时，按 `runtime/*.pid` 中的进程号处理即可（再次运行安装脚本会自动复用已监听的端口，不会重复启动）。

## 7. 端口冲突

默认端口：Web `8000`、MongoDB `27017`、Redis `6379`。若被占用：

- 安装时用 `--port` / `-Port` 换 Web 端口；
- MongoDB / Redis 端口被占用时脚本会提示（端口已监听则直接复用），需要隔离时用 `--mongo-port` / `--redis-port`。

## 8. 常见问题

| 现象 | 处理 |
|------|------|
| 下载 MongoDB / Redis 很慢或失败 | 加 `--mirror <镜像前缀>`（或 `-Mirror`）换源，或重试（脚本带 3 次重试） |
| Linux 报 `python3-venv` 缺失 | `sudo apt install python3-venv`（Debian 系）或 `sudo dnf install python3.11`（RHEL 系）后重跑脚本 |
| Redis 阶段很慢 | RHEL 系默认源码编译 Redis（约几分钟）；有 root 时 apt 系统会直接装系统包 |
| 启动失败，5 分钟内未就绪 | 查看 `logs/server.err.log` 最后 20 行；常见原因：端口被占、pip 安装失败（可 `--mirror` 换 PyPI 源） |
| 忘记管理员密码 | 编辑 `.env` 的 `ADMIN_DEFAULT_PASSWORD`，重启服务 |
| CentOS 7 提示 glibc 过旧 | 升级系统或使用 Docker 部署（`docker-deployment-guide.md`） |
| 想彻底卸载 | 删除安装目录即可（含数据）；只想清数据则删除 `data/` 后重跑脚本 |

## 9. 一键安装 vs Docker

| 维度 | 一键安装 | Docker |
|------|---------|--------|
| 适合 | 单机长期使用、不想装 Docker | 已有 Docker 环境、多版本隔离 |
| 依赖 | Python 3.11+（脚本会自动补装） | Docker + Compose |
| 数据 | 安装目录 `data/` | 卷 |
| 端口 | 默认 8000 | 默认 8080 |

详见 [Docker 部署指南](https://github.com/hsliuping/TradingAgents-CN/blob/community/docs/02-user-guide/getting-started/docker-deployment-guide.md)。
