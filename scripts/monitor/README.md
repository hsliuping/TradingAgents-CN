# 进程监控守护进程

## 功能说明

进程监控守护进程用于监控 TradingAgents-CN 系统的关键进程状态，包括：

- **Worker 进程** - 分析任务处理进程
- **Backend API** - FastAPI 后端服务
- **Nginx** - Web 服务器
- **Redis** - 缓存服务器
- **MongoDB** - 数据库服务器

## 主要功能

1. **定时扫描进程状态** - 默认每 30 秒检查一次
2. **检测进程退出** - 自动检测进程异常退出
3. **记录退出信息** - 记录退出代码、退出时间、错误信息
4. **状态变化告警** - 当进程状态发生变化时输出告警
5. **历史记录** - 保存进程状态历史，便于分析

## 使用方法

### 启动监控守护进程

#### 方法 1: 使用 PowerShell 脚本（推荐）

```powershell
# 前台运行（可以看到实时日志）
.\scripts\monitor\start_monitor.ps1

# 后台运行
.\scripts\monitor\start_monitor.ps1 -Background

# 自定义监控间隔（秒）
.\scripts\monitor\start_monitor.ps1 -Interval 60

# 自定义日志文件
.\scripts\monitor\start_monitor.ps1 -LogFile "logs\monitor.log"
```

#### 方法 2: 使用 Python 直接运行

```bash
python scripts\monitor\process_monitor.py --interval 30 --log-file logs\process_monitor.log
```

#### 方法 3: 自动启动（集成到 start_all.ps1）

监控守护进程已集成到 `start_all.ps1` 中，会在启动所有服务后自动启动。

### 停止监控守护进程

```powershell
.\scripts\monitor\stop_monitor.ps1
```

或者手动停止：

```powershell
# 查看 PID
Get-Content logs\process_monitor.pid

# 停止进程
Stop-Process -Id <PID>
```

### 查看监控状态

#### 快速查看当前状态（推荐）

```powershell
# 显示简洁的状态摘要
.\scripts\monitor\monitor_status.ps1

# JSON 格式输出（便于脚本处理）
.\scripts\monitor\monitor_status.ps1 -Json
```

#### 查看监控日志

```powershell
# 查看最后 50 行日志
.\scripts\monitor\view_monitor.ps1

# 查看最后 100 行日志
.\scripts\monitor\view_monitor.ps1 -Tail 100

# 实时跟踪日志（类似 tail -f）
.\scripts\monitor\view_monitor.ps1 -Follow

# 显示状态摘要
.\scripts\monitor\view_monitor.ps1 -Status
```

#### 在启动界面查看监控状态

当使用 `start_all.ps1` 启动所有服务时，监控守护进程会在后台运行。主循环会每 30 秒自动显示一次监控状态摘要，您可以在启动界面直接看到监控情况。

## 日志文件

- **监控日志**: `logs/process_monitor.log` - 记录所有监控事件
- **历史记录**: `logs/process_monitor_history.json` - 保存进程状态历史
- **PID 文件**: `logs/process_monitor.pid` - 守护进程的进程 ID

## 日志示例

### 进程正常启动

```
2026-01-20 13:00:00 - __main__ - INFO - ✅ [Worker] 进程已启动
   PID: 12345
   命令行: python app\worker\__main__.py
   内存: 125.50 MB
```

### 进程异常退出

```
2026-01-20 13:05:30 - __main__ - ERROR - ❌ [Worker] 进程已退出！
   之前 PID: 12345
   当前状态: not_found
   退出代码: 1
   退出时间: 2026-01-20T13:05:30
   命令行: python app\worker\__main__.py
   💡 建议: 检查日志文件或系统事件查看器获取详细错误信息
```

### 进程重启

```
2026-01-20 13:10:00 - __main__ - WARNING - ⚠️ [Worker] 进程已重启
   旧 PID: 12345
   新 PID: 12346
   退出代码: 0
```

## 配置选项

### 命令行参数

- `--interval`: 检查间隔（秒），默认 30 秒
- `--log-file`: 日志文件路径，默认 `logs/process_monitor.log`
- `--pid-file`: PID 文件路径，默认 `logs/process_monitor.pid`
- `--history-file`: 历史记录文件路径，默认 `logs/process_monitor_history.json`

### 监控间隔建议

- **开发环境**: 30 秒（默认）
- **生产环境**: 60-120 秒（减少系统开销）
- **调试模式**: 10-15 秒（快速发现问题）

## 依赖要求

### 必需

- Python 3.8+
- Windows PowerShell（Windows 系统）

### 可选（推荐）

- `psutil` - 提供更准确的进程信息（推荐安装）
  ```bash
  pip install psutil
  ```

如果不安装 `psutil`，监控器会使用 PowerShell 方法，功能相同但可能稍慢。

## 故障排查

### 监控守护进程无法启动

1. 检查 Python 是否可用
2. 检查日志目录是否存在（`logs/`）
3. 检查是否有权限写入日志文件

### 无法检测到进程

1. 确认进程名称匹配（检查 `process_monitor.py` 中的进程模式）
2. 如果使用 PowerShell 方法，确保有管理员权限
3. 安装 `psutil` 以获得更好的进程检测能力

### 误报进程退出

1. 检查进程是否真的在运行
2. 查看历史记录文件了解状态变化
3. 调整监控间隔，避免进程启动时的短暂检测窗口

## 集成到系统服务

可以将监控守护进程配置为 Windows 服务，实现开机自启动：

```powershell
# 使用 NSSM (Non-Sucking Service Manager) 创建服务
nssm install TradingAgentsMonitor "C:\path\to\python.exe" "C:\path\to\scripts\monitor\process_monitor.py --interval 60"
```

## 注意事项

1. **资源占用**: 监控守护进程本身资源占用很小，但频繁检查可能增加系统负载
2. **日志文件**: 定期清理日志文件，避免占用过多磁盘空间
3. **权限要求**: 某些进程信息可能需要管理员权限才能获取
4. **进程匹配**: 进程匹配基于名称和命令行参数，确保配置正确

## 扩展功能

可以扩展监控守护进程以支持：

- 邮件/短信告警
- 自动重启失败的进程
- Web 界面查看状态
- 性能指标收集
- 集成到监控系统（如 Prometheus）
