# 开发环境启动指南

## 📋 概述

本项目提供了三种开发环境启动方式：

1. **PowerShell 脚本** (`start_dev.ps1`) - 推荐 Windows 用户使用
2. **Python 脚本** (`start_dev.py`) - 跨平台，适合 Linux/Mac
3. **进程守护程序** (`scripts/monitor/process_monitor.py`) - 带自动重启功能

---

## 🚀 方式 1: PowerShell 脚本（推荐）

### 基本用法

```powershell
# 启动 Backend + Worker（最常用）
.\start_dev.ps1

# 只启动 Backend
.\start_dev.ps1 -BackendOnly

# 只启动 Worker
.\start_dev.ps1 -WorkerOnly

# 启动 Backend，不启动 Worker
.\start_dev.ps1 -NoWorker

# 使用自定义端口
.\start_dev.ps1 -BackendPort 8080

# 查看帮助
.\start_dev.ps1 -Help
```

### 特性

- ✅ 自动检测虚拟环境（venv/env/vendors）
- ✅ 自动设置 UTF-8 编码
- ✅ 实时显示日志输出
- ✅ Ctrl+C 同时停止所有进程
- ✅ 进程异常退出时自动提示

### 输出示例

```
========================================
TradingAgents-CN Development Mode
========================================

[OK] Found Python: C:\TradingAgentsCN\venv\Scripts\python.exe
[OK] UTF-8 encoding enabled

[1/2] Starting Backend API...
  Port: 8000
  URL: http://127.0.0.1:8000
  Docs: http://127.0.0.1:8000/docs

[OK] Backend started (Job ID: 1)

[2/2] Starting Worker...
  Log: logs\worker.log

[OK] Worker started (Job ID: 2)

========================================
Development server running!
========================================

Press Ctrl+C to stop all processes
```

---

## 🐍 方式 2: Python 脚本

### 基本用法

```bash
# 启动 Backend + Worker
python start_dev.py

# 只启动 Backend
python start_dev.py --backend-only

# 只启动 Worker
python start_dev.py --worker-only

# 启动 Backend，不启动 Worker
python start_dev.py --no-worker

# 使用自定义端口
python start_dev.py --port 8080
```

### 特性

- ✅ 跨平台（Windows/Linux/Mac）
- ✅ 自动检测虚拟环境
- ✅ 自动设置 UTF-8 编码
- ✅ 进程管理（Ctrl+C 停止所有）
- ✅ 进程异常退出检测

---

## 🔧 方式 3: 进程守护程序（带自动重启）

### 适用场景

- 长时间运行的开发环境
- 需要自动重启功能（Worker 崩溃后自动恢复）
- 需要监控所有服务状态

### 启动方式

```powershell
# 启动守护程序（带自动重启）
.\scripts\monitor\start_monitor.ps1 -Background -AutoRestart

# 查看状态
.\scripts\monitor\monitor_status.ps1

# 查看日志
.\scripts\monitor\view_monitor.ps1

# 实时查看日志
.\scripts\monitor\view_monitor.ps1 -Follow

# 停止守护程序
.\scripts\monitor\stop_monitor.ps1
```

### 自动重启配置

- **监控进程**: Backend, Worker, MongoDB, Redis, Nginx
- **自动重启**: Worker 和 Backend（其他服务不自动重启）
- **重启限制**: 5 分钟内最多重启 3 次
- **重启延迟**: 10 秒

---

## 📊 对比

| 特性 | PowerShell 脚本 | Python 脚本 | 守护程序 |
|------|----------------|-------------|---------|
| **实时日志** | ✅ | ✅ | ❌（写入文件） |
| **自动重启** | ❌ | ❌ | ✅ |
| **跨平台** | ❌（仅 Windows） | ✅ | ✅ |
| **简单易用** | ✅✅✅ | ✅✅ | ✅ |
| **监控所有服务** | ❌ | ❌ | ✅ |
| **适合调试** | ✅✅✅ | ✅✅ | ❌ |
| **适合生产** | ❌ | ❌ | ✅ |

---

## 💡 推荐使用场景

### 日常开发调试
```powershell
# 推荐：PowerShell 脚本（实时日志，方便调试）
.\start_dev.ps1
```

### 长时间运行测试
```powershell
# 推荐：守护程序（自动重启，无需人工干预）
.\scripts\monitor\start_monitor.ps1 -Background -AutoRestart
```

### 只测试 Backend API
```powershell
# 推荐：PowerShell 脚本（快速启动）
.\start_dev.ps1 -BackendOnly
```

### 只测试 Worker
```powershell
# 推荐：PowerShell 脚本
.\start_dev.ps1 -WorkerOnly
```

---

## 🔍 常见问题

### Q: 如何查看 Worker 日志？

**A**: Worker 日志在 `logs/worker.log`

```powershell
# 查看最新日志
Get-Content logs\worker.log -Tail 50

# 实时查看日志
Get-Content logs\worker.log -Tail 50 -Wait
```

### Q: Backend 启动失败怎么办？

**A**: 检查端口是否被占用

```powershell
# 检查 8000 端口
netstat -ano | findstr :8000

# 使用其他端口
.\start_dev.ps1 -BackendPort 8080
```

### Q: Worker 一直重启怎么办？

**A**: 查看 Worker 日志，检查错误原因

```powershell
# 查看 Worker 日志
Get-Content logs\worker.log -Tail 100

# 如果是配置问题，检查数据库连接
# 如果是代码问题，修复后重启
```

---

## 📝 提交到 Git

```bash
git add start_dev.ps1 start_dev.py DEV_STARTUP_GUIDE.md
git commit -m "Add development startup scripts

- start_dev.ps1: PowerShell script for Windows
- start_dev.py: Python script for cross-platform
- DEV_STARTUP_GUIDE.md: Usage guide

Features:
- Auto-detect virtual environment
- UTF-8 encoding enabled
- Real-time log output
- Ctrl+C stops all processes"
```

