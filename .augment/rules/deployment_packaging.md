# 部署和打包规则

## 📦 三种打包方式

TradingAgents-CN Pro 支持三种部署打包方式：

### 1. Docker 部署打包

**用途**: 跨平台部署，适合服务器环境

**核心文件**:
- `Dockerfile.backend` - 后端服务镜像（FastAPI + Python 3.10）
- `Dockerfile.frontend` - 前端服务镜像（Vue 3 + Vite + Nginx）
- `docker-compose.yml` - Docker Compose 配置（前后端分离）
- `docker/nginx.conf` - Nginx 配置（前端静态文件服务）

**构建脚本**:
- `scripts/build-amd64.ps1` / `scripts/build-amd64.sh` - AMD64 架构构建
- `scripts/build-arm64.sh` - ARM64 架构构建
- `scripts/build-multiarch.ps1` / `scripts/build-multiarch.sh` - 多架构构建
- `scripts/docker-init.ps1` / `scripts/docker-init.sh` - Docker 初始化

**服务架构**:
```
Docker Compose 服务栈:
├── backend (FastAPI)      - 端口 8000
├── frontend (Vue 3)       - 端口 80
├── mongodb (MongoDB 4.4)  - 端口 27017
├── redis (Redis 7)        - 端口 6379
└── nginx (反向代理)       - 端口 80
```

**构建命令**:
```bash
# 构建所有镜像
docker-compose build

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

**文档位置**:
- `docs/deployment/docker/DOCKER_DEPLOYMENT_v1.0.0.md`
- `docs/deployment/docker/DOCKER_FILES_README.md`

---

### 2. 绿色便携版（Portable Package）

**用途**: Windows 免安装版本，解压即用

**核心目录**:
```
release/TradingAgentsCN-portable/
├── vendors/                    # 嵌入式运行时
│   ├── python/                 # Python 3.10.11 嵌入式版本
│   ├── mongodb/                # MongoDB 便携版
│   ├── redis/                  # Redis 便携版
│   └── nginx/                  # Nginx 便携版
├── app/                        # 后端代码（编译为 .pyc）
├── core/                       # 核心代码（编译为 .pyc）
│   └── licensing/              # 许可证模块（Cython 编译为 .pyd）
├── tradingagents/              # v1.x 代码（保留源码）
├── frontend/dist/              # 前端构建产物
├── install/                    # 数据库配置文件
├── scripts/                    # 工具脚本
├── data/                       # 数据目录
├── logs/                       # 日志目录
├── .env                        # 环境配置
└── start_all.ps1               # 启动脚本
```

**构建脚本**:
- `scripts/deployment/build_portable_package.ps1` - 主构建脚本
- `scripts/deployment/sync_to_portable_pro.ps1` - Pro 版同步脚本
- `scripts/deployment/compile_pro_complete.ps1` - 代码编译脚本
- `scripts/deployment/setup_embedded_python.ps1` - 嵌入式 Python 设置

**构建流程**:
```powershell
# 完整构建（同步 + 编译 + 打包）
.\scripts\deployment\build_portable_package.ps1

# 只同步和编译，不打包
.\scripts\deployment\build_portable_package.ps1 -SkipPackage

# 跳过同步，使用现有文件
.\scripts\deployment\build_portable_package.ps1 -SkipSync
```

**代码保护**:
- ✅ `core/licensing/` - Cython 编译为 `.pyd`（最强保护）
- ✅ `core/` 其他模块 - 字节码编译为 `.pyc`
- ✅ `app/` - 字节码编译为 `.pyc`
- ✅ `tradingagents/` - 保留源码（开源部分）

**输出文件**:
- 位置: `release/packages/`
- 命名: `TradingAgentsCN-Pro-Portable-{VERSION}-{TIMESTAMP}.zip`
- 大小: ~350 MB（压缩后）

**文档位置**:
- `scripts/deployment/README_PRO_PACKAGING.md`

---

### 3. Windows 安装包（NSIS Installer）

**用途**: Windows 标准安装程序，带安装向导

**核心目录**:
```
scripts/windows-installer/
├── build/
│   └── build_installer.ps1     # 主构建脚本
├── nsis/
│   └── installer.nsi           # NSIS 安装脚本
├── prepare/
│   ├── build_portable.ps1      # 准备便携版
│   └── probe_ports.ps1         # 端口探测
└── README.md
```

**构建脚本**:
- `scripts/windows-installer/build/build_installer.ps1` - 主构建脚本

**构建流程**:
```powershell
# 自动读取版本号构建
.\scripts\windows-installer\build\build_installer.ps1

# 跳过便携版构建（使用现有）
.\scripts\windows-installer\build\build_installer.ps1 -SkipPortablePackage

# 指定版本号
.\scripts\windows-installer\build\build_installer.ps1 -Version "1.0.1"
```

**安装程序特性**:
- ✅ 端口配置 UI（Backend, MongoDB, Redis, Nginx）
- ✅ 自动端口冲突检测
- ✅ UTF-8 编码支持
- ✅ 桌面和开始菜单快捷方式
- ✅ 卸载程序和注册表集成

**输出文件**:
- 位置: `scripts/windows-installer/nsis/`
- 命名: `TradingAgentsCNSetup-{VERSION}.exe`
- 大小: ~320 MB（LZMA 压缩，94.5% 压缩率）

**文档位置**:
- `scripts/windows-installer/README.md`
- `docs/WINDOWS_INSTALLER_OPTIMIZATION.md`

---

## 🔧 构建参数对比

| 参数 | Docker | 便携版 | 安装包 |
|------|--------|--------|--------|
| **版本号** | 镜像标签 | 文件名 | 自动读取 VERSION 文件 |
| **代码保护** | 容器隔离 | 编译为 .pyc/.pyd | 同便携版 |
| **运行时** | Docker 镜像 | 嵌入式 Python | 同便携版 |
| **数据库** | Docker 容器 | 便携版 MongoDB | 同便携版 |
| **配置** | .env + docker-compose | .env | 安装向导 |
| **大小** | ~1.5 GB（镜像） | ~350 MB（压缩） | ~320 MB（压缩） |

---

## 📝 构建顺序建议

### 完整发布流程

```powershell
# 1. 更新版本号
echo "1.0.0" > VERSION

# 2. 构建便携版（包含代码编译）
.\scripts\deployment\build_portable_package.ps1

# 3. 构建 Windows 安装包（基于便携版）
.\scripts\windows-installer\build\build_installer.ps1 -SkipPortablePackage

# 4. 构建 Docker 镜像
docker-compose build

# 5. 推送 Docker 镜像到 Docker Hub
.\scripts\publish-docker-images.ps1
```

---

## 🎯 使用场景

### Docker 部署
- ✅ 服务器部署
- ✅ 跨平台支持（Linux, macOS, Windows）
- ✅ 容器化管理
- ✅ 自动扩展

### 绿色便携版
- ✅ 快速试用
- ✅ 无需安装权限
- ✅ 便于移动和备份
- ✅ 开发测试

### Windows 安装包
- ✅ 标准 Windows 安装体验
- ✅ 开始菜单集成
- ✅ 卸载程序
- ✅ 企业部署

---

**最后更新**: 2026-01-05  
**相关文档**:
- Docker: `docs/deployment/docker/`
- 便携版: `scripts/deployment/README_PRO_PACKAGING.md`
- 安装包: `scripts/windows-installer/README.md`

