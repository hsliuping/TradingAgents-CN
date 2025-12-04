# TradingAgents-CN 绿色安装版使用手册

## 📦 简介

TradingAgents-CN 绿色安装版是一个**免安装、开箱即用**的便携版本，无需复杂的环境配置，适合快速部署和测试。

### ✨ 特点

- ✅ **免安装**：解压即用，无需安装 Python、MongoDB、Redis 等依赖
- ✅ **便携式**：所有依赖打包在一起，可以放在 U 盘或移动硬盘中
- ✅ **隔离环境**：不影响系统环境，可以与其他版本共存
- ✅ **一键启动**：提供启动脚本，一键启动所有服务
- ✅ **数据独立**：数据库和配置文件都在安装目录内，便于备份和迁移

---

## 📋 系统要求

### 最低配置

- **操作系统**：Windows 10/11 (64位)
- **CPU**：双核处理器
- **内存**：4GB RAM
- **磁盘空间**：5GB 可用空间
- **网络**：需要联网访问数据源 API

### 推荐配置

- **操作系统**：Windows 10/11 (64位)
- **CPU**：四核或更高
- **内存**：8GB RAM 或更高
- **磁盘空间**：10GB 可用空间
- **网络**：稳定的网络连接

---

## 🚀 快速开始

### 第一步：解压安装包

1. 下载 `TradingAgentsCN-Portable-vX.X.X.zip` 或 `.7z` 安装包
2. 解压到任意目录（建议路径不包含中文和空格）
   ```
   例如：D:\TradingAgentsCN-portable
   ```
3. **重要**：确保解压后的目录结构完整，包含以下关键文件：
   - `start_all.ps1` - 启动脚本
   - `install/database_export_config_2025-10-31.json` - 配置文件
   - `scripts/import_config_and_create_user.py` - 导入脚本
3. 解压后的目录结构：
   ```
   TradingAgentsCN-portable/
   ├── app/                    # 后端应用代码
   ├── tradingagents/          # 核心库代码
   ├── web/                    # 前端代码
   ├── vendors/                # 第三方依赖
   │   ├── mongodb/            # MongoDB 数据库
   │   ├── redis/              # Redis 缓存
   │   ├── nginx/              # Nginx 服务器
   │   └── python/             # Python 环境
   ├── data/                   # 数据目录
   │   ├── mongodb/            # MongoDB 数据文件
   │   ├── redis/              # Redis 数据文件
   │   └── cache/              # 缓存文件
   ├── logs/                   # 日志目录
   ├── config/                 # 配置文件
   ├── scripts/                # 脚本目录
   │   └── installer/          # 安装和启动脚本
   ├── .env                    # 环境变量配置
   └── README.md               # 说明文档
   ```

### 第二步：初始化环境

1. 以**管理员身份**运行 PowerShell
2. 进入安装目录：
   ```powershell
   cd D:\TradingAgentsCN-portable
   ```
3. 运行初始化脚本：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\installer\setup.ps1
   ```
4. 等待初始化完成（约 2-5 分钟）

**初始化脚本会执行以下操作**：
- ✅ 检查系统环境
- ✅ 创建必要的目录
- ✅ 初始化 MongoDB 数据库
- ✅ 配置 Redis 缓存
- ✅ 配置 Nginx 服务器
- ✅ 安装 Python 依赖包
- ✅ 创建默认配置文件

### 第三步：配置 API 密钥

1. 编辑 `.env` 文件（使用记事本或其他文本编辑器）
2. 配置数据源 API 密钥：

   ```env
   # Tushare API Token (推荐)
   TUSHARE_TOKEN=your_tushare_token_here
   
   # Finnhub API Key (可选)
   FINNHUB_API_KEY=your_finnhub_key_here
   
   # LLM API Keys (用于 AI 分析功能)
   OPENAI_API_KEY=your_openai_key_here
   DEEPSEEK_API_KEY=your_deepseek_key_here
   ```

3. 保存文件

**如何获取 API 密钥**：
- **Tushare**：访问 https://tushare.pro/ 注册并获取 Token
- **Finnhub**：访问 https://finnhub.io/ 注册并获取 API Key
- **OpenAI**：访问 https://platform.openai.com/ 获取 API Key
- **DeepSeek**：访问 https://platform.deepseek.com/ 获取 API Key

### 第四步：启动服务

1. 在安装目录下，右键点击 `start_all.ps1`，选择"使用 PowerShell 运行"

   或者在 PowerShell 中执行：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\start_all.ps1
   ```

2. **首次启动说明**：
   - 第一次启动时，系统会自动导入配置数据和创建默认管理员账号（admin/admin123）
   - 这个过程只在首次启动时执行一次，后续启动会自动跳过
   - 如果需要重新导入配置，可以使用 `-ForceImport` 参数：
     ```powershell
     powershell -ExecutionPolicy Bypass -File .\start_all.ps1 -ForceImport
     ```

3. 等待所有服务启动（首次约 1 分钟，后续约 30 秒）

4. 看到以下提示表示启动成功：
   ```
   ========================================
   All Services Started Successfully!
   ========================================

   Service Status:
     MongoDB:  127.0.0.1:27017
     Redis:    127.0.0.1:6379
     Backend:  http://127.0.0.1:8000
     Frontend: http://127.0.0.1:80

   Access the application:
     Web UI:   http://localhost
     API Docs: http://localhost/docs

   Default Login:
     Username: admin
     Password: admin123
   ```

### 第五步：访问应用

1. 打开浏览器，访问：http://localhost:3000
2. 首次访问会自动跳转到登录页面
3. 使用默认账号登录：
   - **用户名**：admin
   - **密码**：admin123

---

## 🎮 使用指南

### 主要功能

#### 1. 股票数据同步

**功能说明**：从数据源同步股票基础信息、历史行情、实时行情等数据。

**操作步骤**：
1. 点击顶部导航栏的 "数据管理"
2. 选择 "数据同步"
3. 选择要同步的数据类型：
   - **基础信息**：股票代码、名称、行业等
   - **历史行情**：日线、周线、月线数据
   - **实时行情**：当前价格、涨跌幅等
   - **财务数据**：资产负债表、利润表等
4. 点击 "开始同步" 按钮
5. 等待同步完成

**注意事项**：
- 首次同步建议先同步基础信息（约 5-10 分钟）
- 历史行情数据量较大，建议分批同步
- 实时行情仅在交易时间内有效

#### 2. 股票查询与分析

**功能说明**：查询股票信息，查看 K 线图、技术指标、财务数据等。

**操作步骤**：
1. 在首页搜索框输入股票代码或名称
2. 点击搜索结果进入股票详情页
3. 查看以下信息：
   - **基本信息**：股票代码、名称、行业、市值等
   - **实时行情**：当前价格、涨跌幅、成交量等
   - **K 线图**：日线、周线、月线图表
   - **技术指标**：MA、MACD、KDJ、RSI 等
   - **财务数据**：PE、PB、ROE、营收、利润等

#### 3. AI 智能分析

**功能说明**：使用 AI 多智能体系统对股票进行深度分析。

**操作步骤**：
1. 在股票详情页点击 "AI 分析" 按钮
2. 选择分析类型：
   - **快速分析**：基于技术指标的快速判断
   - **深度分析**：多维度综合分析
   - **多智能体辩论**：多个 AI 智能体进行辩论分析
3. 等待分析完成（约 30 秒 - 2 分钟）
4. 查看分析报告

**注意事项**：
- AI 分析需要配置 LLM API 密钥
- 分析结果仅供参考，不构成投资建议

#### 4. 自选股管理

**功能说明**：添加和管理自选股列表。

**操作步骤**：
1. 在股票详情页点击 "加入自选" 按钮
2. 在首页点击 "自选股" 标签查看自选股列表
3. 点击 "移除" 按钮可以从自选股中移除

---

## 🔧 管理与维护

### 启动和停止服务

#### 启动所有服务
```powershell
powershell -ExecutionPolicy Bypass -File scripts\installer\start_all.ps1
```

#### 停止所有服务
```powershell
powershell -ExecutionPolicy Bypass -File scripts\installer\stop_all.ps1
```

#### 重启所有服务
```powershell
powershell -ExecutionPolicy Bypass -File scripts\installer\restart_all.ps1
```

#### 查看服务状态
```powershell
powershell -ExecutionPolicy Bypass -File scripts\installer\status.ps1
```

### 单独管理服务

#### MongoDB
```powershell
# 启动
scripts\installer\start_mongodb.ps1

# 停止
scripts\installer\stop_mongodb.ps1
```

#### Redis
```powershell
# 启动
scripts\installer\start_redis.ps1

# 停止
scripts\installer\stop_redis.ps1
```

#### Nginx
```powershell
# 启动
scripts\installer\start_nginx.ps1

# 停止
scripts\installer\stop_nginx.ps1
```

#### Backend API
```powershell
# 启动
scripts\installer\start_backend.ps1

# 停止
scripts\installer\stop_backend.ps1
```

### 日志查看

日志文件位置：
- **MongoDB**：`logs/mongodb.log`
- **Redis**：`logs/redis.log`
- **Nginx**：`logs/nginx_access.log` 和 `logs/nginx_error.log`
- **Backend API**：`logs/api.log`

查看实时日志：
```powershell
# 查看后端 API 日志
Get-Content logs\api.log -Tail 50 -Wait

# 查看 MongoDB 日志
Get-Content logs\mongodb.log -Tail 50 -Wait
```

### 数据备份

#### 备份数据库
```powershell
# 备份 MongoDB 数据
powershell -ExecutionPolicy Bypass -File scripts\maintenance\backup_mongodb.ps1

# 备份到指定目录
powershell -ExecutionPolicy Bypass -File scripts\maintenance\backup_mongodb.ps1 -OutputDir "D:\Backups"
```

#### 恢复数据库
```powershell
# 恢复 MongoDB 数据
powershell -ExecutionPolicy Bypass -File scripts\maintenance\restore_mongodb.ps1 -BackupFile "backup_20250102_120000.zip"
```

### 清理缓存

```powershell
# 清理所有缓存
powershell -ExecutionPolicy Bypass -File scripts\maintenance\cleanup_cache.ps1

# 清理指定类型的缓存
powershell -ExecutionPolicy Bypass -File scripts\maintenance\cleanup_cache.ps1 -Type "market_data"
```

---

## ⚙️ 配置说明

### 环境变量配置 (.env)

主要配置项说明：

```env
# ============================================================================
# 数据源配置
# ============================================================================

# Tushare API Token (推荐使用)
TUSHARE_TOKEN=your_token_here

# AKShare (无需 API Key，但数据有限)
USE_AKSHARE=true

# BaoStock (无需 API Key，但数据有限)
USE_BAOSTOCK=true

# Finnhub API Key (美股数据)
FINNHUB_API_KEY=your_key_here

# ============================================================================
# LLM 配置 (AI 分析功能)
# ============================================================================

# OpenAI
USE_OPENAI=true
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://api.openai.com/v1

# DeepSeek
USE_DEEPSEEK=true
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ============================================================================
# 数据库配置
# ============================================================================

# MongoDB
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_USER=admin
MONGODB_PASSWORD=tradingagents123
MONGODB_DATABASE=tradingagents

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=tradingagents123
REDIS_DB=0

# ============================================================================
# 应用配置
# ============================================================================

# 后端 API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# 前端
FRONTEND_PORT=3000

# JWT 密钥 (用于用户认证)
JWT_SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# ============================================================================
# 日志配置
# ============================================================================

LOG_LEVEL=INFO
LOG_FILE=logs/api.log
LOG_MAX_SIZE=100MB
LOG_BACKUP_COUNT=10
```

---

## ❓ 常见问题

### Q1: 启动失败，提示端口被占用

**问题**：启动时提示 "Port 8000 is already in use" 或类似错误。

**解决方案**：
1. 检查是否有其他程序占用了端口：
   ```powershell
   netstat -ano | findstr "8000"
   netstat -ano | findstr "3000"
   netstat -ano | findstr "27017"
   netstat -ano | findstr "6379"
   ```
2. 关闭占用端口的程序，或修改 `.env` 文件中的端口配置

### Q2: 无法访问前端页面

**问题**：浏览器访问 http://localhost:3000 显示无法连接。

**解决方案**：
1. 检查 Nginx 是否启动：
   ```powershell
   Get-Process nginx -ErrorAction SilentlyContinue
   ```
2. 查看 Nginx 错误日志：
   ```powershell
   Get-Content logs\nginx_error.log -Tail 20
   ```
3. 尝试重启 Nginx：
   ```powershell
   scripts\installer\stop_nginx.ps1
   scripts\installer\start_nginx.ps1
   ```

### Q3: 数据同步失败

**问题**：点击 "开始同步" 后提示错误或一直显示 "同步中"。

**解决方案**：
1. 检查 API 密钥是否正确配置
2. 检查网络连接是否正常
3. 查看后端日志：
   ```powershell
   Get-Content logs\api.log -Tail 50
   ```
4. 尝试使用其他数据源

### Q4: AI 分析功能无法使用

**问题**：点击 "AI 分析" 后提示错误或无响应。

**解决方案**：
1. 检查是否配置了 LLM API 密钥
2. 检查 API 密钥是否有效
3. 检查网络连接是否正常
4. 查看后端日志中的错误信息

### Q5: MongoDB 启动失败

**问题**：启动时提示 "MongoDB failed to start"。

**解决方案**：
1. 检查 MongoDB 日志：
   ```powershell
   Get-Content logs\mongodb.log -Tail 50
   ```
2. 检查数据目录权限
3. 尝试删除 `data\mongodb\db\mongod.lock` 文件后重启
4. 如果数据损坏，可以删除 `data\mongodb\db` 目录后重新初始化

### Q6: 如何更新到新版本

**解决方案**：
1. 备份当前数据：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\maintenance\backup_mongodb.ps1
   ```
2. 停止所有服务：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\installer\stop_all.ps1
   ```
3. 下载新版本安装包
4. 解压到新目录
5. 复制旧版本的 `.env` 文件到新目录
6. 恢复数据库备份（如需要）
7. 启动新版本服务

---

## 📞 技术支持

### 获取帮助

- **GitHub Issues**：https://github.com/yourusername/TradingAgentsCN/issues
- **文档**：查看 `docs/` 目录下的详细文档
- **示例代码**：查看 `examples/` 目录下的示例

### 报告问题

报告问题时，请提供以下信息：
1. 操作系统版本
2. 错误信息截图
3. 相关日志文件内容
4. 复现步骤

---

## 📄 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

---

## 🙏 致谢

感谢以下开源项目：
- FastAPI
- Vue.js
- MongoDB
- Redis
- Nginx
- Tushare
- AKShare
- BaoStock

---

**祝您使用愉快！** 🎉

