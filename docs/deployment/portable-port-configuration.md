# 绿色版端口配置说明

## 📋 概述

TradingAgents-CN 绿色版使用以下端口：

| 服务 | 默认端口 | 说明 | 配置文件 |
|------|---------|------|---------|
| **前端 (Nginx)** | **80** | Web界面访问端口 | `runtime/nginx.conf` |
| **后端 (FastAPI)** | **8000** | API服务端口 | `.env` |
| **MongoDB** | **27017** | 数据库端口 | `runtime/mongodb.conf` (自动生成) |
| **Redis** | **6379** | 缓存服务端口 | `runtime/redis.conf` |

---

## 🔧 修改前端端口（Nginx - 默认80）

### 方法：修改 `runtime/nginx.conf`

**步骤：**

1. **打开配置文件**：
   ```
   runtime/nginx.conf
   ```

2. **找到第 36 行**：
   ```nginx
   server {
       listen       80;
       server_name  localhost;
   ```

3. **修改端口号**（例如改为 8080）：
   ```nginx
   server {
       listen       8080;
       server_name  localhost;
   ```

4. **保存文件**

5. **重启服务**：
   - 停止所有服务：双击运行 `stop_all.ps1`
   - 启动所有服务：双击运行 `start_all.ps1`

6. **访问新地址**：
   ```
   http://localhost:8080
   ```

### ⚠️ 注意事项

- **端口冲突检查**：修改前请确保新端口未被占用
- **防火墙设置**：如果使用非标准端口，可能需要配置防火墙规则
- **浏览器缓存**：修改后建议清除浏览器缓存

---

## 🔧 修改后端端口（FastAPI - 默认8000）

### 方法：修改 `.env` 文件

**步骤：**

1. **打开配置文件**：
   ```
   .env
   ```

2. **找到以下配置**（大约在第 534-535 行）：
   ```ini
   HOST=0.0.0.0
   PORT=8000
   ```

3. **修改端口号**（例如改为 8001）：
   ```ini
   HOST=0.0.0.0
   PORT=8001
   ```

4. **同时修改 Nginx 配置**：
   
   打开 `runtime/nginx.conf`，找到第 31-33 行：
   ```nginx
   # Backend upstream
   upstream backend {
       server 127.0.0.1:8000;
   }
   ```
   
   修改为新端口：
   ```nginx
   # Backend upstream
   upstream backend {
       server 127.0.0.1:8001;
   }
   ```

5. **保存所有文件**

6. **重启服务**：
   - 停止所有服务：双击运行 `stop_all.ps1`
   - 启动所有服务：双击运行 `start_all.ps1`

7. **验证**：
   - 前端访问：`http://localhost` (或你修改的前端端口)
   - 后端API文档：`http://localhost/docs`

### ⚠️ 重要提示

**修改后端端口时，必须同时修改两个文件：**
1. `.env` - 后端服务监听端口
2. `runtime/nginx.conf` - Nginx 代理目标端口

**如果只修改一个文件，会导致前端无法连接后端！**

---

## 🔧 修改 MongoDB 端口（默认27017）

### 方法：修改启动脚本

MongoDB 的配置文件是在启动时自动生成的，需要修改启动脚本。

**步骤：**

1. **打开启动脚本**：
   ```
   scripts/installer/start_services_clean.ps1
   ```

2. **找到 MongoDB 启动部分**（大约在第 100-150 行）：
   ```powershell
   $mongoArgs = @(
       "--dbpath", "`"$mongoDbPath`"",
       "--logpath", "`"$mongoLogPath`"",
       "--port", "27017",
       ...
   )
   ```

3. **修改端口号**（例如改为 27018）：
   ```powershell
   $mongoArgs = @(
       "--dbpath", "`"$mongoDbPath`"",
       "--logpath", "`"$mongoLogPath`"",
       "--port", "27018",
       ...
   )
   ```

4. **修改 `.env` 文件**：
   
   打开 `.env`，找到 MongoDB 配置（大约在第 228-233 行）：
   ```ini
   MONGODB_HOST=localhost
   MONGODB_PORT=27017
   ```
   
   修改为新端口：
   ```ini
   MONGODB_HOST=localhost
   MONGODB_PORT=27018
   ```

5. **保存所有文件**

6. **重启服务**

---

## 🔧 修改 Redis 端口（默认6379）

### 方法：修改 `runtime/redis.conf`

**步骤：**

1. **打开配置文件**：
   ```
   runtime/redis.conf
   ```

2. **找到端口配置**（大约在第 10-20 行）：
   ```
   port 6379
   ```

3. **修改端口号**（例如改为 6380）：
   ```
   port 6380
   ```

4. **修改 `.env` 文件**：
   
   打开 `.env`，找到 Redis 配置（大约在第 238-241 行）：
   ```ini
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```
   
   修改为新端口：
   ```ini
   REDIS_HOST=localhost
   REDIS_PORT=6380
   ```

5. **保存所有文件**

6. **重启服务**

---

## 📝 完整示例：修改所有端口

假设你想修改所有端口以避免冲突：

| 服务 | 原端口 | 新端口 |
|------|-------|-------|
| 前端 (Nginx) | 80 | 8080 |
| 后端 (FastAPI) | 8000 | 8001 |
| MongoDB | 27017 | 27018 |
| Redis | 6379 | 6380 |

### 需要修改的文件：

1. **`runtime/nginx.conf`**：
   ```nginx
   # 第 36 行：前端端口
   listen       8080;
   
   # 第 32 行：后端代理端口
   upstream backend {
       server 127.0.0.1:8001;
   }
   ```

2. **`.env`**：
   ```ini
   # 后端端口
   HOST=0.0.0.0
   PORT=8001
   
   # MongoDB 端口
   MONGODB_HOST=localhost
   MONGODB_PORT=27018
   
   # Redis 端口
   REDIS_HOST=localhost
   REDIS_PORT=6380
   ```

3. **`scripts/installer/start_services_clean.ps1`**：
   ```powershell
   # MongoDB 启动参数
   "--port", "27018",
   ```

4. **`runtime/redis.conf`**：
   ```
   port 6380
   ```

### 重启服务：

```powershell
# 停止所有服务
.\stop_all.ps1

# 启动所有服务
.\start_all.ps1
```

### 访问新地址：

```
http://localhost:8080
```

---

## 🔍 检查端口占用

### Windows PowerShell 命令：

```powershell
# 检查 80 端口
Get-NetTCPConnection -LocalPort 80 -State Listen

# 检查 8000 端口
Get-NetTCPConnection -LocalPort 8000 -State Listen

# 检查 27017 端口
Get-NetTCPConnection -LocalPort 27017 -State Listen

# 检查 6379 端口
Get-NetTCPConnection -LocalPort 6379 -State Listen
```

### 查看占用端口的进程：

```powershell
# 查看所有监听端口
netstat -ano | findstr LISTENING

# 查看特定端口（例如 80）
netstat -ano | findstr :80
```

---

## ❓ 常见问题

### Q1: 修改端口后无法访问？

**A:** 检查以下几点：
1. 确认所有相关配置文件都已修改
2. 确认服务已重启
3. 检查防火墙是否阻止了新端口
4. 查看日志文件：`logs/nginx_error.log`、`logs/backend_error.log`

### Q2: 前端可以访问，但 API 调用失败？

**A:** 这通常是因为：
1. `.env` 中的后端端口已修改
2. 但 `runtime/nginx.conf` 中的 `upstream backend` 端口未修改
3. 解决方法：确保两个文件中的后端端口一致

### Q3: 修改后服务无法启动？

**A:** 检查：
1. 新端口是否被其他程序占用
2. 配置文件语法是否正确（特别是 nginx.conf）
3. 查看错误日志：`logs/nginx_error.log`、`logs/backend_startup.log`

### Q4: 如何恢复默认端口？

**A:** 
1. 重新解压绿色版压缩包
2. 或者按照本文档将端口改回默认值：
   - 前端：80
   - 后端：8000
   - MongoDB：27017
   - Redis：6379

---

## 📞 技术支持

如果遇到问题，请：

1. 查看日志文件：
   - `logs/nginx_error.log` - Nginx 错误日志
   - `logs/backend_error.log` - 后端错误日志
   - `logs/tradingagents.log` - 应用日志

2. 运行诊断脚本：
   ```powershell
   .\diagnose.ps1
   ```

3. 提交 Issue：
   - GitHub: https://github.com/your-repo/TradingAgents-CN/issues
   - 请附上错误日志和配置文件内容

---

## 📚 相关文档

- [绿色版快速启动指南](../guides/portable-quick-start.md)
- [绿色版详细说明](../deployment/portable-deployment.md)
- [故障排除指南](../troubleshooting/common-issues.md)

---

**最后更新**: 2025-11-05

