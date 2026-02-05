# MongoDB和Redis诊断脚本使用说明

## 概述

`debug_services.ps1` 是一个独立的诊断工具，用于检测和调试MongoDB、Redis服务的启动状态和错误信息。

## 功能特性

- ✅ **进程检查**: 检查服务进程是否运行
- ✅ **端口检查**: 检查服务端口是否被监听
- ✅ **连接测试**: 测试TCP连接和认证连接
- ✅ **启动尝试**: 可以尝试启动未运行的服务
- ✅ **日志捕获**: 显示服务启动时的详细日志
- ✅ **错误诊断**: 提供详细的错误分析和修复建议

## 使用方法

### 基本用法

```powershell
# 诊断所有服务（MongoDB和Redis）
.\scripts\installer\debug_services.ps1

# 只诊断MongoDB
.\scripts\installer\debug_services.ps1 -Service mongodb

# 只诊断Redis
.\scripts\installer\debug_services.ps1 -Service redis
```

### 启动服务

```powershell
# 诊断并尝试启动MongoDB（如果未运行）
.\scripts\installer\debug_services.ps1 -Service mongodb -Start

# 诊断并尝试启动Redis（如果未运行）
.\scripts\installer\debug_services.ps1 -Service redis -Start

# 诊断并尝试启动所有服务
.\scripts\installer\debug_services.ps1 -Service all -Start
```

### 显示启动日志

```powershell
# 启动MongoDB并显示详细日志
.\scripts\installer\debug_services.ps1 -Service mongodb -Start -ShowLogs

# 启动Redis并显示详细日志
.\scripts\installer\debug_services.ps1 -Service redis -Start -ShowLogs
```

### 测试连接

```powershell
# 诊断MongoDB并测试连接
.\scripts\installer\debug_services.ps1 -Service mongodb -TestConnection

# 诊断Redis并测试连接
.\scripts\installer\debug_services.ps1 -Service redis -TestConnection
```

### 组合使用

```powershell
# 诊断、启动、显示日志并测试连接
.\scripts\installer\debug_services.ps1 -Service mongodb -Start -ShowLogs -TestConnection
```

## 参数说明

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `-Service` | String | 要诊断的服务 (`mongodb`, `redis`, `all`) | `all` |
| `-Start` | Switch | 如果服务未运行，尝试启动它 | `false` |
| `-ShowLogs` | Switch | 显示服务启动时的详细日志输出 | `false` |
| `-TestConnection` | Switch | 测试服务的TCP连接和认证连接 | `false` |

## 诊断输出说明

### 成功状态
- ✅ **绿色**: 服务运行正常
- ✅ **绿色**: 检查通过

### 警告信息
- ⚠️ **黄色**: 需要注意的问题（如端口被占用、权限问题等）

### 错误信息
- ❌ **红色**: 服务存在问题（进程未运行、端口未监听等）

### 详细信息
- 📋 **灰色**: 配置信息、进程信息等详细信息
- 🔍 **青色**: 正在进行的检查
- 💡 **青色**: 修复建议

## 常见问题诊断

### MongoDB启动失败

**问题**: MongoDB进程启动后立即退出

**可能原因**:
1. 端口被占用
2. 数据目录权限不足
3. 数据文件损坏
4. 配置文件错误

**解决方法**:
```powershell
# 1. 查看详细错误信息
.\scripts\installer\debug_services.ps1 -Service mongodb -Start -ShowLogs

# 2. 检查端口占用
netstat -ano | findstr :27017

# 3. 检查数据目录权限
icacls "data\mongodb\db"

# 4. 以管理员身份运行
# 右键PowerShell -> 以管理员身份运行
```

### Redis启动失败

**问题**: Redis进程启动后立即退出

**可能原因**:
1. 端口被占用
2. 配置文件错误
3. 数据目录权限不足

**解决方法**:
```powershell
# 1. 查看详细错误信息
.\scripts\installer\debug_services.ps1 -Service redis -Start -ShowLogs

# 2. 检查配置文件
cat runtime\redis.conf

# 3. 检查端口占用
netstat -ano | findstr :6379
```

### 端口被占用

**问题**: 端口被其他进程占用

**解决方法**:
```powershell
# 1. 查看占用端口的进程
netstat -ano | findstr :27017  # MongoDB端口
netstat -ano | findstr :6379   # Redis端口

# 2. 停止占用端口的进程（替换PID为实际进程ID）
Stop-Process -Id <PID> -Force

# 3. 或修改.env文件使用其他端口
# MONGODB_PORT=27018
# REDIS_PORT=6380
```

### 连接测试失败

**问题**: TCP连接成功但认证失败

**可能原因**:
1. 用户名或密码错误
2. 认证源配置错误
3. 用户未创建

**解决方法**:
```powershell
# 1. 检查.env文件中的认证信息
# MONGODB_USERNAME=admin
# MONGODB_PASSWORD=tradingagents123
# REDIS_PASSWORD=tradingagents123

# 2. 重新初始化MongoDB用户
.\scripts\init_mongodb.ps1
```

## 配置说明

脚本会从以下位置读取配置：

1. **.env文件**: 项目根目录下的 `.env` 文件
2. **默认值**: 如果.env文件中没有配置，使用以下默认值：
   - MongoDB端口: `27017`
   - Redis端口: `6379`
   - MongoDB主机: `localhost`
   - Redis主机: `localhost`
   - MongoDB用户名: `admin`
   - MongoDB密码: `tradingagents123`
   - Redis密码: `tradingagents123`

## 注意事项

1. **权限要求**: 
   - 某些操作（如启动服务、检查端口）可能需要管理员权限
   - 如果遇到权限问题，请以管理员身份运行PowerShell

2. **Python依赖**:
   - 连接测试功能需要Python和相应的库（pymongo, redis）
   - 如果Python不可用，脚本仍会进行TCP连接测试

3. **服务路径**:
   - MongoDB路径: `vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\mongod.exe`
   - Redis路径: `vendors\redis\Redis-8.2.2-Windows-x64-msys2\redis-server.exe`
   - 如果路径不同，请修改脚本中的路径配置

4. **数据目录**:
   - MongoDB数据目录: `data\mongodb\db`
   - Redis数据目录: `data\redis\data`
   - 脚本会自动创建不存在的目录

## 示例输出

```
========================================
TradingAgents-CN 服务诊断工具
========================================

📋 加载配置文件...
  ✅ 找到 .env 文件: C:\TradingAgentsCN\.env

========================================
MongoDB 诊断
========================================

📋 配置信息:
  主机: localhost
  端口: 27017
  用户名: admin

🔍 检查MongoDB可执行文件...
  ✅ MongoDB可执行文件存在

🔍 检查数据目录...
  ✅ 数据目录存在: C:\TradingAgentsCN\data\mongodb\db

🔍 检查MongoDB进程...
  ✅ MongoDB进程正在运行
    PID: 12345
    路径: C:\TradingAgentsCN\vendors\mongodb\...\mongod.exe
    启动时间: 2026-02-02 10:00:00

🔍 检查端口 27017...
  ✅ 端口 27017 正在监听
    进程: mongod (PID: 12345)

📊 诊断摘要:
  ✅ MongoDB运行正常
```

## 相关文件

- `start_services_clean.ps1`: 服务启动脚本
- `start_all.ps1`: 完整启动脚本（包括后端和Nginx）
- `.env`: 环境配置文件

## 故障排除

如果脚本无法正常工作，请检查：

1. PowerShell执行策略：
   ```powershell
   Get-ExecutionPolicy
   # 如果需要，设置为RemoteSigned
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

2. 脚本路径：
   ```powershell
   # 确保在项目根目录运行
   cd C:\TradingAgentsCN
   ```

3. 文件权限：
   ```powershell
   # 检查脚本文件权限
   Get-Acl .\scripts\installer\debug_services.ps1
   ```

## 更新日志

- **v1.0.0** (2026-02-02): 初始版本
  - 支持MongoDB和Redis诊断
  - 支持启动服务和日志捕获
  - 支持连接测试
  - 提供详细的错误诊断和修复建议
