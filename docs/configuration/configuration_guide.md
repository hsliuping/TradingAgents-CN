# TradingAgents-CN 配置指南

> **目标读者**: 新用户、系统管理员
> 
> **阅读时间**: 10分钟
> 
> **更新日期**: 2025-10-04

---

## 📋 目录

1. [快速开始](#1-快速开始)
2. [必需配置](#2-必需配置)
3. [推荐配置](#3-推荐配置)
4. [Web界面配置](#4-web界面配置)
5. [高级配置](#5-高级配置)
6. [常见问题](#6-常见问题)
7. [故障排查](#7-故障排查)

---

## 1. 快速开始

### 1.1 最小化配置（5分钟）

只需配置 `.env` 文件中的必需项，即可启动系统。

#### 步骤1: 复制配置模板

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

#### 步骤2: 编辑必需配置

打开 `.env` 文件，配置以下必需项：

```bash
# ===== 必需配置 =====

# 数据库连接
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_USERNAME=admin
MONGODB_PASSWORD=your_password_here  # 修改为你的密码
MONGODB_DATABASE=tradingagents

# Redis连接
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password_here    # 修改为你的密码

# 安全配置
JWT_SECRET=your-secret-key-change-in-production  # 修改为随机字符串
CSRF_SECRET=your-csrf-secret-key                 # 修改为随机字符串
```

#### 步骤3: 启动系统

```bash
# 启动后端
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端（新终端）
cd frontend
npm run dev
```

#### 步骤4: 访问系统

- **前端界面**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

#### 步骤5: 首次登录

默认管理员账号：
- **用户名**: `admin`
- **密码**: `admin123`

⚠️ **重要**: 首次登录后请立即修改密码！

---

## 2. 必需配置

### 2.1 数据库配置

#### MongoDB（必需）

用于存储股票数据、分析结果、用户信息等。

```bash
# [REQUIRED] MongoDB连接配置
MONGODB_HOST=localhost          # MongoDB主机地址
MONGODB_PORT=27017              # MongoDB端口
MONGODB_USERNAME=admin          # MongoDB用户名
MONGODB_PASSWORD=xxx            # MongoDB密码
MONGODB_DATABASE=tradingagents  # 数据库名称
MONGODB_AUTH_SOURCE=admin       # 认证数据库
```

**获取方式**:
- **本地开发**: 使用 `scripts/start_services_alt_ports.bat` 启动本地MongoDB
- **Docker**: 使用 `docker-compose up -d` 启动容器化MongoDB
- **云服务**: 使用 MongoDB Atlas 等云服务

#### Redis（必需）

用于缓存、会话管理、实时通知等。

```bash
# [REQUIRED] Redis连接配置
REDIS_HOST=localhost      # Redis主机地址
REDIS_PORT=6379           # Redis端口
REDIS_PASSWORD=xxx        # Redis密码（可选）
REDIS_DB=0                # Redis数据库编号
```

**获取方式**:
- **本地开发**: 使用 `scripts/start_services_alt_ports.bat` 启动本地Redis
- **Docker**: 使用 `docker-compose up -d` 启动容器化Redis
- **云服务**: 使用 Redis Cloud 等云服务

### 2.2 安全配置

#### JWT密钥（必需）

用于生成和验证用户认证令牌。

```bash
# [REQUIRED] JWT配置
JWT_SECRET=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
```

**生成方式**:
```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32
```

⚠️ **安全提示**:
- 使用至少32字符的随机字符串
- 生产环境必须修改默认值
- 不要将密钥提交到代码仓库

#### CSRF密钥（必需）

用于防止跨站请求伪造攻击。

```bash
# [REQUIRED] CSRF保护
CSRF_SECRET=your-csrf-secret-key-change-in-production
```

---

## 3. 推荐配置

### 3.1 大模型API密钥（推荐）

至少配置一个大模型API密钥，用于AI分析功能。

#### DeepSeek（推荐，性价比高）

```bash
# [RECOMMENDED] DeepSeek API密钥
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_ENABLED=true
```

**获取地址**: https://platform.deepseek.com/
- 注册账号 → 创建API Key → 复制密钥

#### 通义千问（推荐，国产稳定）

```bash
# [RECOMMENDED] 阿里百炼API密钥
DASHSCOPE_API_KEY=sk-xxx
```

**获取地址**: https://dashscope.aliyun.com/
- 注册阿里云账号 → 开通百炼服务 → 获取API密钥

#### 其他大模型（可选）

```bash
# OpenAI
OPENAI_API_KEY=sk-xxx

# Google Gemini
GOOGLE_API_KEY=xxx

# 智谱AI
ZHIPU_API_KEY=xxx
```

### 3.2 数据源配置（推荐）

#### Tushare（推荐，专业A股数据）

```bash
# [RECOMMENDED] Tushare Token
TUSHARE_TOKEN=xxx
TUSHARE_ENABLED=true
```

**获取地址**: https://tushare.pro/register?reg=tacn
- 注册账号 → 邮箱验证 → 获取Token

#### AKShare（推荐，免费无需密钥）

```bash
# [RECOMMENDED] AKShare配置
DEFAULT_CHINA_DATA_SOURCE=akshare
AKSHARE_UNIFIED_ENABLED=true
```

**特点**: 免费、无需API密钥、数据丰富

#### FinnHub（推荐，美股数据）

```bash
# [RECOMMENDED] FinnHub API密钥
FINNHUB_API_KEY=xxx
```

**获取地址**: https://finnhub.io/
- 注册账号 → 获取免费API密钥（60次/分钟）

---

## 4. Web界面配置

### 4.1 访问配置管理

1. 登录系统
2. 点击左侧菜单 **"设置"**
3. 选择 **"配置管理"**

### 4.2 配置大模型

#### 步骤1: 添加厂家

1. 进入 **"厂家管理"** 标签
2. 点击 **"添加厂家"** 按钮
3. 填写厂家信息：
   - 厂家名称（如：DeepSeek）
   - 显示名称（如：DeepSeek）
   - 描述
   - API Base URL
4. 点击 **"保存"**

#### 步骤2: 添加模型配置

1. 进入 **"大模型配置"** 标签
2. 点击 **"添加配置"** 按钮
3. 填写模型信息：
   - 选择厂家
   - 模型名称（如：deepseek-chat）
   - API密钥（如果 `.env` 中已配置，会自动读取）
   - 最大Token数
   - 温度参数
4. 点击 **"测试连接"** 验证配置
5. 点击 **"保存"**

#### 步骤3: 设置默认模型

1. 在模型列表中找到要设置为默认的模型
2. 点击 **"设为默认"** 按钮

### 4.3 配置数据源

#### 步骤1: 添加数据源

1. 进入 **"数据源配置"** 标签
2. 点击 **"添加数据源"** 按钮
3. 填写数据源信息：
   - 数据源类型（Tushare/AKShare/FinnHub等）
   - 数据源名称
   - API密钥（如需要）
   - 优先级
4. 点击 **"测试连接"** 验证配置
5. 点击 **"保存"**

#### 步骤2: 设置默认数据源

1. 在数据源列表中找到要设置为默认的数据源
2. 点击 **"设为默认"** 按钮

### 4.4 系统设置

1. 进入 **"系统设置"** 标签
2. 调整运行时参数：
   - 最大并发任务数
   - 缓存TTL
   - Worker心跳间隔
   - SSE轮询超时
3. 点击 **"保存"** 应用设置

### 4.5 配置导入导出

#### 导出配置

1. 进入 **"导入导出"** 标签
2. 点击 **"导出配置"** 按钮
3. 选择要导出的配置类型
4. 下载 JSON 文件

#### 导入配置

1. 进入 **"导入导出"** 标签
2. 点击 **"导入配置"** 按钮
3. 选择 JSON 文件
4. 预览配置内容
5. 点击 **"确认导入"**

---

## 5. 高级配置

### 5.1 数据同步配置

#### Tushare数据同步

```bash
# Tushare统一数据同步
TUSHARE_UNIFIED_ENABLED=true

# 基础信息同步（每日凌晨2点）
TUSHARE_BASIC_INFO_SYNC_ENABLED=true
TUSHARE_BASIC_INFO_SYNC_CRON="0 2 * * *"

# 实时行情同步（交易时间每5分钟）
TUSHARE_QUOTES_SYNC_ENABLED=true
TUSHARE_QUOTES_SYNC_CRON="*/5 9-15 * * 1-5"

# 历史数据同步（工作日16点）
TUSHARE_HISTORICAL_SYNC_ENABLED=true
TUSHARE_HISTORICAL_SYNC_CRON="0 16 * * 1-5"
```

#### AKShare数据同步

```bash
# AKShare统一数据同步
AKSHARE_UNIFIED_ENABLED=true

# 基础信息同步（每日凌晨3点）
AKSHARE_BASIC_INFO_SYNC_ENABLED=true
AKSHARE_BASIC_INFO_SYNC_CRON="0 3 * * *"

# 实时行情同步（交易时间每10分钟）
AKSHARE_QUOTES_SYNC_ENABLED=true
AKSHARE_QUOTES_SYNC_CRON="*/10 9-15 * * 1-5"
```

### 5.2 性能优化配置

```bash
# 连接池配置
MONGO_MAX_CONNECTIONS=100
MONGO_MIN_CONNECTIONS=10
REDIS_MAX_CONNECTIONS=20

# 并发控制
DEFAULT_USER_CONCURRENT_LIMIT=3
GLOBAL_CONCURRENT_LIMIT=50

# 缓存配置
CACHE_TTL=3600
SCREENING_CACHE_TTL=1800

# 队列配置
QUEUE_MAX_SIZE=10000
QUEUE_VISIBILITY_TIMEOUT=300
```

### 5.3 日志配置

```bash
# 日志级别（DEBUG/INFO/WARNING/ERROR）
LOG_LEVEL=INFO

# 日志格式
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 日志文件
LOG_FILE=logs/tradingagents.log
```

---

## 6. 常见问题

### Q1: 启动时提示缺少配置怎么办？

**A**: 检查 `.env` 文件中的必需配置项是否都已填写。参考 [必需配置](#2-必需配置) 章节。

### Q2: 如何生成安全的JWT密钥？

**A**: 使用以下命令生成：
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Q3: 大模型API密钥配置后不生效？

**A**: 
1. 检查 `.env` 文件中的密钥是否正确
2. 重启后端服务
3. 在Web界面检查模型是否已启用

### Q4: 数据源连接失败怎么办？

**A**:
1. 检查API密钥是否正确
2. 检查网络连接
3. 查看后端日志获取详细错误信息

### Q5: 如何修改默认端口？

**A**: 在 `.env` 文件中修改：
```bash
PORT=8000  # 后端端口
```

前端端口在 `frontend/vite.config.ts` 中修改。

### Q6: Docker部署时如何配置？

**A**: 修改 `.env` 文件中的主机名：
```bash
MONGODB_HOST=mongodb  # Docker服务名
REDIS_HOST=redis      # Docker服务名
```

---

## 7. 故障排查

### 7.1 启动失败

#### 症状: 后端启动失败

**检查步骤**:
1. 检查 MongoDB 是否运行
   ```bash
   # Windows
   sc query MongoDB
   
   # Linux
   systemctl status mongod
   ```

2. 检查 Redis 是否运行
   ```bash
   # Windows
   sc query Redis
   
   # Linux
   systemctl status redis
   ```

3. 检查端口是否被占用
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Linux
   lsof -i :8000
   ```

4. 查看后端日志
   ```bash
   tail -f logs/tradingagents.log
   ```

### 7.2 配置不生效

#### 症状: 修改配置后不生效

**解决方案**:
1. 重启后端服务
2. 清除浏览器缓存
3. 检查配置优先级（环境变量 > 数据库 > 默认值）
4. 查看后端日志确认配置已加载

### 7.3 数据库连接失败

#### 症状: 无法连接到 MongoDB

**解决方案**:
1. 检查 MongoDB 服务是否运行
2. 检查连接配置是否正确
3. 检查防火墙设置
4. 测试连接：
   ```bash
   mongosh "mongodb://admin:password@localhost:27017/tradingagents?authSource=admin"
   ```

### 7.4 API密钥无效

#### 症状: 大模型API调用失败

**解决方案**:
1. 检查API密钥是否正确
2. 检查API密钥是否过期
3. 检查账户余额是否充足
4. 在Web界面测试连接

---

## 8. 配置检查清单

使用此清单确保配置完整：

### 基础配置
- [ ] 已复制 `.env.example` 为 `.env`
- [ ] 已配置 MongoDB 连接
- [ ] 已配置 Redis 连接
- [ ] 已配置 JWT_SECRET
- [ ] 已配置 CSRF_SECRET

### 大模型配置
- [ ] 至少配置了一个大模型API密钥
- [ ] 已在Web界面添加模型配置
- [ ] 已测试模型连接
- [ ] 已设置默认模型

### 数据源配置
- [ ] 已配置至少一个数据源
- [ ] 已测试数据源连接
- [ ] 已设置默认数据源

### 系统验证
- [ ] 后端启动成功
- [ ] 前端启动成功
- [ ] 可以正常登录
- [ ] 可以访问配置管理页面

---

## 9. 获取帮助

### 文档资源
- **项目文档**: `docs/` 目录
- **API文档**: http://localhost:8000/docs
- **配置分析**: `docs/configuration_analysis.md`

### 社区支持
- **GitHub Issues**: 提交问题和建议
- **讨论区**: 参与讨论和交流

### 技术支持
- **邮件**: [待补充]
- **微信群**: [待补充]

---

**祝你使用愉快！** 🎉

