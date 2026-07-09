# TradingAgents-CN Stop Services Guide

[中文版本](#中文版本) | [English Version](#english-version)

---

## 中文版本

### 概述

本文档说明如何停止 TradingAgents-CN 绿色版的所有服务。

### 停止服务的方法

#### 方法 1: 使用批处理文件（推荐）

**最简单的方法**，双击运行：

```
停止所有服务.bat
```

或者在命令行中运行：

```cmd
stop_all_services.bat
```

这个批处理文件会自动调用 PowerShell 脚本停止所有服务。

#### 方法 2: 使用 PowerShell 脚本

在 PowerShell 中运行：

```powershell
# 正常停止（推荐）
.\stop_all.ps1

# 强制停止所有相关进程
.\stop_all.ps1 -Force

# 仅使用 PID 文件停止
.\stop_all.ps1 -OnlyPid

# 静默模式（减少输出）
.\stop_all.ps1 -Quiet
```

#### 方法 3: 使用 Ctrl+C

如果服务是在前台运行的（例如通过 `start_portable.ps1` 启动），可以直接按 `Ctrl+C` 停止。

### 停止服务的流程

`stop_all.ps1` 脚本会按以下步骤停止服务：

#### 步骤 1: 使用 PID 文件停止（优雅停止）

脚本会读取 `runtime\pids.json` 文件，按以下顺序停止服务：

1. **Nginx** - 先尝试优雅停止（`nginx -s quit`），失败则强制停止
2. **Backend (FastAPI)** - 停止 Python 后端进程
3. **Redis** - 停止 Redis 服务
4. **MongoDB** - 停止 MongoDB 服务

#### 步骤 2: 强制停止所有相关进程（兜底方案）

如果 PID 文件不存在或某些进程停止失败，脚本会强制停止以下进程：

- `nginx.exe` - Nginx Web 服务器
- `python.exe` / `pythonw.exe` - Python 后端进程
- `redis-server.exe` - Redis 服务
- `mongod.exe` - MongoDB 服务

#### 步骤 3: 清理临时文件

脚本会清理以下文件和目录：

- `runtime\pids.json` - PID 文件
- `logs\nginx.pid` - Nginx PID 文件
- `temp\*` - 临时目录中的文件

#### 步骤 4: 验证服务状态

脚本会检查是否还有相关进程在运行，并给出提示。

### 常见问题

#### Q1: 运行脚本后提示"仍有进程在运行"

**原因**：某些进程可能没有正常停止。

**解决方法**：

1. 再次运行 `.\stop_all.ps1 -Force` 强制停止
2. 或者手动在任务管理器中结束这些进程

#### Q2: 提示"无法停止进程，拒绝访问"

**原因**：进程可能以管理员权限运行。

**解决方法**：

1. 右键点击 `停止所有服务.bat`，选择"以管理员身份运行"
2. 或者在管理员权限的 PowerShell 中运行 `.\stop_all.ps1`

#### Q3: 停止服务后，下次启动失败

**原因**：可能是端口被占用或数据文件损坏。

**解决方法**：

1. 运行 `.\diagnose.ps1` 诊断问题
2. 检查 `logs\` 目录中的日志文件
3. 如果是端口占用，参考 `端口配置说明.md` 修改端口

#### Q4: 如何只停止某个服务？

**方法 1**：使用任务管理器手动停止对应进程

**方法 2**：修改 `stop_all.ps1` 脚本，注释掉不需要停止的服务

**方法 3**：使用 PowerShell 命令：

```powershell
# 停止 Nginx
Get-Process -Name nginx -ErrorAction SilentlyContinue | Stop-Process -Force

# 停止 Backend
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force

# 停止 Redis
Get-Process -Name redis-server -ErrorAction SilentlyContinue | Stop-Process -Force

# 停止 MongoDB
Get-Process -Name mongod -ErrorAction SilentlyContinue | Stop-Process -Force
```

### 参数说明

#### `-Force`

强制停止所有相关进程，不使用 PID 文件。

**使用场景**：
- PID 文件丢失或损坏
- 正常停止失败
- 需要确保所有进程都被停止

**示例**：
```powershell
.\stop_all.ps1 -Force
```

#### `-OnlyPid`

仅使用 PID 文件停止服务，不进行强制停止。

**使用场景**：
- 只想停止通过启动脚本启动的服务
- 避免误杀其他 Python/MongoDB/Redis 进程

**示例**：
```powershell
.\stop_all.ps1 -OnlyPid
```

#### `-Quiet`

静默模式，减少输出信息。

**使用场景**：
- 在自动化脚本中使用
- 不需要详细的输出信息

**示例**：
```powershell
.\stop_all.ps1 -Quiet
```

### 服务停止顺序说明

脚本按以下顺序停止服务，这是推荐的停止顺序：

1. **Nginx** - 先停止前端服务，避免新的请求进入
2. **Backend** - 停止后端 API 服务
3. **Redis** - 停止缓存服务
4. **MongoDB** - 最后停止数据库服务

这个顺序确保：
- 不会有新的请求进入系统
- 正在处理的请求有时间完成
- 数据能够正确保存

### 安全提示

1. **数据安全**：停止服务前，确保没有重要的分析任务正在运行
2. **优雅停止**：优先使用正常停止方式，避免数据损坏
3. **备份数据**：定期备份 `data\` 目录中的数据
4. **检查日志**：停止服务后，检查 `logs\` 目录中的日志，确认没有错误

---

## English Version

### Overview

This document explains how to stop all TradingAgents-CN portable version services.

### Methods to Stop Services

#### Method 1: Using Batch File (Recommended)

**Simplest method**, double-click to run:

```
stop_all_services.bat
```

Or run in command line:

```cmd
stop_all_services.bat
```

This batch file will automatically call the PowerShell script to stop all services.

#### Method 2: Using PowerShell Script

Run in PowerShell:

```powershell
# Normal stop (recommended)
.\stop_all.ps1

# Force stop all related processes
.\stop_all.ps1 -Force

# Only use PID file to stop
.\stop_all.ps1 -OnlyPid

# Quiet mode (reduce output)
.\stop_all.ps1 -Quiet
```

#### Method 3: Using Ctrl+C

If services are running in foreground (e.g., started via `start_portable.ps1`), you can press `Ctrl+C` to stop.

### Service Stop Process

The `stop_all.ps1` script stops services in the following steps:

#### Step 1: Stop Using PID File (Graceful Stop)

The script reads `runtime\pids.json` file and stops services in this order:

1. **Nginx** - Try graceful stop first (`nginx -s quit`), force stop if failed
2. **Backend (FastAPI)** - Stop Python backend process
3. **Redis** - Stop Redis service
4. **MongoDB** - Stop MongoDB service

#### Step 2: Force Stop All Related Processes (Fallback)

If PID file doesn't exist or some processes fail to stop, the script will force stop:

- `nginx.exe` - Nginx web server
- `python.exe` / `pythonw.exe` - Python backend processes
- `redis-server.exe` - Redis service
- `mongod.exe` - MongoDB service

#### Step 3: Cleanup Temporary Files

The script cleans up:

- `runtime\pids.json` - PID file
- `logs\nginx.pid` - Nginx PID file
- `temp\*` - Files in temporary directories

#### Step 4: Verify Service Status

The script checks if any related processes are still running and provides suggestions.

### Common Issues

#### Q1: Script reports "processes still running"

**Cause**: Some processes may not have stopped properly.

**Solution**:

1. Run `.\stop_all.ps1 -Force` again to force stop
2. Or manually terminate these processes in Task Manager

#### Q2: "Access denied" error when stopping processes

**Cause**: Processes may be running with administrator privileges.

**Solution**:

1. Right-click `stop_all_services.bat` and select "Run as administrator"
2. Or run `.\stop_all.ps1` in PowerShell with administrator privileges

#### Q3: Services fail to start after stopping

**Cause**: Port may be occupied or data files corrupted.

**Solution**:

1. Run `.\diagnose.ps1` to diagnose issues
2. Check log files in `logs\` directory
3. If port is occupied, refer to port configuration guide

#### Q4: How to stop only specific services?

**Method 1**: Manually stop corresponding processes in Task Manager

**Method 2**: Modify `stop_all.ps1` script, comment out services you don't want to stop

**Method 3**: Use PowerShell commands:

```powershell
# Stop Nginx
Get-Process -Name nginx -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop Backend
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop Redis
Get-Process -Name redis-server -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop MongoDB
Get-Process -Name mongod -ErrorAction SilentlyContinue | Stop-Process -Force
```

### Parameter Description

#### `-Force`

Force stop all related processes without using PID file.

**Use Cases**:
- PID file is missing or corrupted
- Normal stop failed
- Need to ensure all processes are stopped

**Example**:
```powershell
.\stop_all.ps1 -Force
```

#### `-OnlyPid`

Only use PID file to stop services, no force stop.

**Use Cases**:
- Only want to stop services started by startup script
- Avoid killing other Python/MongoDB/Redis processes

**Example**:
```powershell
.\stop_all.ps1 -OnlyPid
```

#### `-Quiet`

Quiet mode, reduce output.

**Use Cases**:
- Use in automation scripts
- Don't need detailed output

**Example**:
```powershell
.\stop_all.ps1 -Quiet
```

### Service Stop Order

The script stops services in this recommended order:

1. **Nginx** - Stop frontend service first to prevent new requests
2. **Backend** - Stop backend API service
3. **Redis** - Stop cache service
4. **MongoDB** - Stop database service last

This order ensures:
- No new requests enter the system
- Ongoing requests have time to complete
- Data is saved correctly

### Safety Tips

1. **Data Safety**: Ensure no important analysis tasks are running before stopping services
2. **Graceful Stop**: Prefer normal stop method to avoid data corruption
3. **Backup Data**: Regularly backup data in `data\` directory
4. **Check Logs**: After stopping services, check logs in `logs\` directory for errors

---

**Last Updated**: 2025-11-05

