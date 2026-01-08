# Docker 部署初始化指南

## 概述

本指南帮助您在新机器上使用 `docker-compose.hub.yml` 部署 TradingAgents-CN 后，解决登录错误并准备必要的基础数据。

## 问题描述

新机器部署后可能遇到的登录问题：
- 前端登录提示用户名或密码错误
- 后端 API 认证失败
- 数据库缺少基础数据
- 系统配置未初始化

## 解决方案

我们提供了三个初始化脚本来解决这些问题：

### 1. 快速修复脚本（推荐）

**适用场景**：仅需解决登录问题

```bash
# Python 脚本
python scripts/quick_login_fix.py

# PowerShell 脚本（Windows）
.\scripts\docker_init.ps1 -QuickFix
```

**功能**：
- 修复管理员密码配置
- 创建 Web 应用用户配置
- 检查并创建基础 MongoDB 数据
- 验证 .env 文件

### 2. 完整初始化脚本

**适用场景**：全新部署，需要完整的系统初始化

```bash
# Python 脚本
python scripts/docker_deployment_init.py

# PowerShell 脚本（Windows）
.\scripts\docker_init.ps1 -FullInit
```

**功能**：
- 检查 Docker 服务状态
- 等待服务启动完成
- 初始化 MongoDB 数据库（集合、索引、基础数据）
- 创建系统配置和模型配置
- 设置管理员密码
- 创建 .env 文件

### 3. 系统状态检查

**适用场景**：检查系统当前状态

```bash
# PowerShell 脚本（Windows）
.\scripts\docker_init.ps1 -CheckOnly
```

## 使用步骤

### 步骤 1：启动 Docker 服务

```bash
# 启动所有服务
docker-compose -f docker-compose.hub.yml up -d

# 检查服务状态
docker-compose -f docker-compose.hub.yml ps
```

### 步骤 2：等待服务启动

等待 30-60 秒，确保所有服务完全启动。

### 步骤 3：运行初始化脚本

**方式一：快速修复（推荐）**
```bash
python scripts/quick_login_fix.py
```

**方式二：PowerShell 交互式**
```powershell
.\scripts\docker_init.ps1
```

### 步骤 4：验证登录

访问系统并尝试登录：

- **前端应用**: http://localhost:80
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

## 默认登录信息

### 后端 API 登录
- **用户名**: `admin`
- **密码**: 查看 `config/admin_password.json` 文件中的密码
  - 如果文件不存在或为空，默认密码是 `admin123`
  - 当前配置文件中的密码是 `1234567`

### Web 应用登录
- **管理员**: `admin` / `admin123`
- **普通用户**: `user` / `user123`

## 常见问题

### Q1: 登录时提示"用户名或密码错误"

**解决方案**：
1. 检查 `config/admin_password.json` 文件中的密码
2. 运行快速修复脚本：`python scripts/quick_login_fix.py`
3. 使用脚本显示的密码进行登录

### Q2: MongoDB 连接失败

**解决方案**：
1. 确保 MongoDB 容器正在运行：`docker ps | grep mongodb`
2. 检查端口 27017 是否被占用
3. 重启 MongoDB 容器：`docker-compose -f docker-compose.hub.yml restart mongodb`

### Q3: 前端无法访问后端 API

**解决方案**：
1. 检查后端容器状态：`docker ps | grep backend`
2. 查看后端日志：`docker-compose -f docker-compose.hub.yml logs backend`
3. 确保端口 8000 可访问

### Q4: .env 文件配置问题

**解决方案**：
1. 从 `.env.example` 复制创建 `.env` 文件
2. 根据实际情况修改配置
3. 重启服务使配置生效

## 配置文件说明

### config/admin_password.json
```json
{
  "password": "your_admin_password"
}
```

### web/config/users.json
```json
{
  "admin": {
    "password_hash": "hashed_password",
    "role": "admin",
    "permissions": ["analysis", "config", "admin"],
    "created_at": timestamp
  }
}
```

## 安全建议

1. **立即修改默认密码**：首次登录后立即修改管理员密码
2. **配置 API 密钥**：在 `.env` 文件中配置必要的 API 密钥
3. **定期备份**：定期备份数据库和配置文件
4. **网络安全**：在生产环境中配置防火墙和访问控制

## 下一步

1. **配置 API 密钥**：
   - 配置 `DASHSCOPE_API_KEY`（通义千问）
   - 配置 `TUSHARE_TOKEN`（股票数据）
   - 配置其他需要的 API 密钥

2. **初始化股票数据**：
   ```bash
   # 初始化基础股票数据
   python cli/tushare_init.py --basic
   ```

3. **测试系统功能**：
   - 尝试进行股票分析
   - 检查数据同步功能
   - 验证各项功能正常

## 技术支持

如果遇到其他问题，请：
1. 查看容器日志：`docker-compose -f docker-compose.hub.yml logs`
2. 检查系统状态：`.\scripts\docker_init.ps1 -CheckOnly`
3. 提供详细的错误信息和日志

## 脚本文件说明

- `scripts/quick_login_fix.py` - 快速登录修复脚本
- `scripts/docker_deployment_init.py` - 完整系统初始化脚本
- `scripts/docker_init.ps1` - PowerShell 管理脚本
- `scripts/user_password_manager.py` - 用户密码管理工具
