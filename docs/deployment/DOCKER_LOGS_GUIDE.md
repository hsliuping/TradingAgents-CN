# 🐳 TradingAgents Docker 日志管理指南

## 📋 概述

本指南介绍如何在Docker环境中管理和获取TradingAgents的日志文件。

## 🔧 改进内容

### 1. **Docker Compose 配置优化**

在 `docker-compose.yml` 中添加了日志目录映射：

```yaml
volumes:
  - ./logs:/app/logs  # 将容器内日志映射到本地logs目录
```

### 2. **环境变量配置**

添加了详细的日志配置环境变量：

```yaml
environment:
  TRADINGAGENTS_LOG_LEVEL: "INFO"
  TRADINGAGENTS_LOG_DIR: "/app/logs"
  TRADINGAGENTS_LOG_FILE: "/app/logs/tradingagents.log"
  TRADINGAGENTS_LOG_MAX_SIZE: "100MB"
  TRADINGAGENTS_LOG_BACKUP_COUNT: "5"
```

### 3. **Docker 日志配置**

添加了Docker级别的日志轮转：

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "3"
```

## 🚀 使用方法

### **方法1: 使用启动脚本 (推荐)**

#### Linux/macOS:
```bash
# 给脚本执行权限
chmod +x start_docker.sh

# 启动Docker服务
./start_docker.sh
```

#### Windows PowerShell:
```powershell
# 启动Docker服务
.\start_docker.ps1
```

### **方法2: 手动启动**

```bash
# 1. 确保logs目录存在
python ensure_logs_dir.py

# 2. 启动Docker容器
docker-compose up -d

# 3. 检查容器状态
docker-compose ps
```

## 📄 日志文件位置

### **本地日志文件**
- **位置**: `./logs/` 目录
- **主日志**: `logs/tradingagents.log`
- **错误日志**: `logs/tradingagents_error.log` (如果有错误)
- **轮转日志**: `logs/tradingagents.log.1`, `logs/tradingagents.log.2` 等

### **Docker 标准日志**
- **查看命令**: `docker-compose logs web`
- **实时跟踪**: `docker-compose logs -f web`

## 🔍 日志查看方法

### **1. 使用日志查看工具**
```bash
# 交互式日志查看工具
python view_logs.py
```

功能包括：
- 📋 显示所有日志文件
- 👀 查看日志文件内容
- 📺 实时跟踪日志
- 🔍 搜索日志内容
- 🐳 查看Docker日志

### **2. 直接查看文件**

#### Linux/macOS:
```bash
# 查看最新日志
tail -f logs/tradingagents.log

# 查看最后100行
tail -100 logs/tradingagents.log

# 搜索错误
grep -i error logs/tradingagents.log
```

#### Windows PowerShell:
```powershell
# 实时查看日志
Get-Content logs\tradingagents.log -Wait

# 查看最后50行
Get-Content logs\tradingagents.log -Tail 50

# 搜索错误
Select-String -Path logs\tradingagents.log -Pattern "error" -CaseSensitive:$false
```

### **3. Docker 日志命令**
```bash
# 查看容器日志
docker logs TradingAgents-web

# 实时跟踪容器日志
docker logs -f TradingAgents-web

# 查看最近1小时的日志
docker logs --since 1h TradingAgents-web

# 查看最后100行日志
docker logs --tail 100 TradingAgents-web
```

## 📤 获取日志文件

### **发送给开发者的文件**

当遇到问题需要技术支持时，请发送以下文件：

1. **主日志文件**: `logs/tradingagents.log`
2. **错误日志文件**: `logs/tradingagents_error.log` (如果存在)
3. **Docker日志**: 
   ```bash
   docker logs TradingAgents-web > docker_logs.txt 2>&1
   ```

### **快速打包日志**

#### Linux/macOS:
```bash
# 创建日志压缩包
tar -czf tradingagents_logs_$(date +%Y%m%d_%H%M%S).tar.gz logs/ docker_logs.txt
```

#### Windows PowerShell:
```powershell
# 创建日志压缩包
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Compress-Archive -Path logs\*,docker_logs.txt -DestinationPath "tradingagents_logs_$timestamp.zip"
```

## 🔧 故障排除

### **问题1: logs目录为空**

**原因**: 容器内应用可能将日志输出到stdout而不是文件

**解决方案**:
1. 检查Docker日志: `docker-compose logs web`
2. 确认环境变量配置正确
3. 重启容器: `docker-compose restart web`

### **问题2: 权限问题**

**Linux/macOS**:
```bash
# 修复目录权限
sudo chown -R $USER:$USER logs/
chmod 755 logs/
```

**Windows**: 通常无权限问题

### **问题3: 日志文件过大**

**自动轮转**: 配置了自动轮转，主日志文件最大100MB
**手动清理**:
```bash
# 备份并清空日志
cp logs/tradingagents.log logs/tradingagents.log.backup
> logs/tradingagents.log
```

### **问题4: 容器无法启动**

**检查步骤**:
1. 检查Docker状态: `docker info`
2. 检查端口占用: `netstat -tlnp | grep 8501`
3. 查看启动日志: `docker-compose logs web`
4. 检查配置文件: `.env` 文件是否存在

## 📊 日志级别说明

- **DEBUG**: 详细的调试信息，包含函数调用、变量值等
- **INFO**: 一般信息，程序正常运行的关键步骤
- **WARNING**: 警告信息，程序可以继续运行但需要注意
- **ERROR**: 错误信息，程序遇到错误但可以恢复
- **CRITICAL**: 严重错误，程序可能无法继续运行

## 🎯 最佳实践

### **1. 定期检查日志**
```bash
# 每天检查错误日志
grep -i error logs/tradingagents.log | tail -20
```

### **2. 监控日志大小**
```bash
# 检查日志文件大小
ls -lh logs/
```

### **3. 备份重要日志**
```bash
# 定期备份日志
cp logs/tradingagents.log backups/tradingagents_$(date +%Y%m%d).log
```

### **4. 实时监控**
```bash
# 在另一个终端实时监控日志
tail -f logs/tradingagents.log | grep -i "error\|warning"
```

## 📞 技术支持

如果遇到问题：

1. **收集日志**: 使用上述方法收集完整日志
2. **描述问题**: 详细描述问题现象和重现步骤
3. **环境信息**: 提供操作系统、Docker版本等信息
4. **发送文件**: 将日志文件发送给开发者

---

**通过这些改进，现在可以方便地获取和管理TradingAgents的日志文件了！** 🎉