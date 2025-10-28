# TradingAgents-CN v1.0.0-preview 快速开始指南

> 🚀 5分钟快速部署，开始你的AI投资分析之旅！

## 📋 前置要求

### 必需

- **Docker** 20.10+ 和 **Docker Compose** 2.0+ （推荐方式）
  - 或 **Python** 3.10+ 和 **Node.js** 18+（本地开发）
- **至少一个LLM API密钥**（DeepSeek、OpenAI、Google AI等）
- **稳定的互联网连接**

### 推荐

- **Tushare Token**（专业金融数据，免费注册）
- **4GB+内存** 和 **20GB+磁盘空间**

---

## 🚀 方式一：Docker一键部署（推荐）

### 步骤1：克隆仓库

```bash
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN
```

### 步骤2：配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑配置文件（使用你喜欢的编辑器）
nano .env  # 或 vim .env 或 code .env
```

**最小配置**（必需）：

```bash
# 1. 配置至少一个LLM API密钥
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
DEEPSEEK_ENABLED=true

# 2. 配置JWT密钥（生产环境必须修改）
JWT_SECRET=your-super-secret-jwt-key-change-in-production

# 3. 配置数据源（可选，推荐）
TUSHARE_TOKEN=your-tushare-token-here
TUSHARE_ENABLED=true
```

### 步骤3：启动服务

```bash
# 启动所有服务（后台运行）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 步骤4：访问应用

- **前端界面**: http://localhost:5173
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **MongoDB管理**: http://localhost:8082 (可选)
- **Redis管理**: http://localhost:8081 (可选)

### 步骤5：首次登录

1. 打开浏览器访问 http://localhost:5173
2. 使用默认管理员账号登录：
   - 用户名: `admin`
   - 密码: `admin123`
3. **重要**: 登录后立即修改密码！

### 步骤6：开始分析

1. 点击"单股分析"
2. 输入股票代码（如：`000001`、`600036`）
3. 选择分析深度（推荐Level 2）
4. 点击"开始分析"
5. 实时查看分析进度和结果

---

## 💻 方式二：本地开发部署

### 步骤1：克隆仓库

```bash
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN
```

### 步骤2：安装Python依赖

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 步骤3：配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑配置文件
nano .env
```

**本地开发配置**：

```bash
# LLM API密钥
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
DEEPSEEK_ENABLED=true

# 数据库配置（本地）
TRADINGAGENTS_MONGODB_URL=mongodb://localhost:27017/tradingagents
TRADINGAGENTS_REDIS_URL=redis://localhost:6379
TRADINGAGENTS_CACHE_TYPE=redis

# JWT密钥
JWT_SECRET=your-super-secret-jwt-key-change-in-production

# 数据源
TUSHARE_TOKEN=your-tushare-token-here
TUSHARE_ENABLED=true
DEFAULT_CHINA_DATA_SOURCE=akshare
```

### 步骤4：启动数据库服务

```bash
# 使用Docker启动MongoDB和Redis
docker-compose up -d mongodb redis

# 或者使用本地安装的MongoDB和Redis
# 确保MongoDB运行在 localhost:27017
# 确保Redis运行在 localhost:6379
```

### 步骤5：初始化数据库

```bash
# 创建默认管理员用户
python scripts/create_default_users.py

# 同步基础股票数据（可选）
python scripts/sync_stock_basics.py
```

### 步骤6：启动后端服务

```bash
# 开发模式（自动重载）
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用启动脚本
python start_backend.py
```

### 步骤7：启动前端服务（新终端）

```bash
# 进入前端目录
cd frontend

# 安装yarn（如果未安装）
npm install -g yarn

# 安装依赖（必须使用yarn）
yarn install

# 启动开发服务器
yarn dev
```

### 步骤8：访问应用

- **前端界面**: http://localhost:5173
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

---

## 🎯 快速测试

### 测试1：单股分析

```bash
# 使用curl测试API
curl -X POST "http://localhost:8000/api/analysis/single" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "symbol": "000001",
    "market": "A股",
    "research_depth": 2
  }'
```

### 测试2：股票筛选

1. 访问前端界面
2. 点击"智能筛选"
3. 选择预设策略（如"价值投资"）
4. 点击"开始筛选"
5. 查看筛选结果

### 测试3：查看报告

1. 等待分析完成
2. 点击"报告列表"
3. 查看生成的分析报告
4. 导出为JSON或Markdown格式

---

## 🔧 常见问题

### Q1: Docker启动失败

**问题**: `docker-compose up -d` 失败

**解决方案**:
```bash
# 检查Docker是否运行
docker --version
docker-compose --version

# 检查端口占用
netstat -ano | findstr "5173"  # Windows
lsof -i :5173  # macOS/Linux

# 清理并重新启动
docker-compose down -v
docker-compose up -d
```

### Q2: 前端无法连接后端

**问题**: 前端显示"网络错误"

**解决方案**:
```bash
# 检查后端是否运行
curl http://localhost:8000/health

# 检查CORS配置
# 编辑 .env 文件
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# 重启后端服务
docker-compose restart backend
```

### Q3: 分析任务失败

**问题**: 分析任务显示"失败"状态

**解决方案**:
```bash
# 检查日志
docker-compose logs -f backend

# 检查API密钥
# 确保 .env 文件中的API密钥正确

# 检查数据源
# 确保Tushare Token有效或使用AKShare
```

### Q4: MongoDB连接失败

**问题**: 后端无法连接MongoDB

**解决方案**:
```bash
# 检查MongoDB是否运行
docker-compose ps mongodb

# 检查MongoDB日志
docker-compose logs mongodb

# 重启MongoDB
docker-compose restart mongodb

# 检查连接字符串
# .env 文件中的 TRADINGAGENTS_MONGODB_URL 是否正确
```

### Q5: 内存不足

**问题**: 系统运行缓慢或崩溃

**解决方案**:
```bash
# 检查Docker资源限制
# Docker Desktop -> Settings -> Resources
# 建议: 4GB+ 内存

# 减少并发任务数
# 编辑 .env 文件
MAX_CONCURRENT_ANALYSIS_TASKS=1

# 清理缓存
docker-compose exec redis redis-cli FLUSHALL
```

---

## 📚 下一步

### 学习资源

- [完整使用手册](docs/v1.0.0-preview/04-features/USER_MANUAL.md)
- [系统架构](docs/v1.0.0-preview/02-architecture/01-system-architecture.md)
- [API文档](docs/v1.0.0-preview/05-api-reference/01-rest-api.md)
- [开发指南](docs/v1.0.0-preview/06-development/01-development-guide.md)

### 进阶功能

- **批量分析**: 同时分析多只股票
- **智能筛选**: 使用预设策略筛选股票
- **定时任务**: 设置定时分析任务
- **报告导出**: 导出专业分析报告

### 配置优化

- **多LLM配置**: 配置多个LLM实现负载均衡
- **缓存优化**: 配置Redis提升性能
- **数据源优化**: 配置多个数据源提高可靠性

---

## 🤝 获取帮助

### 官方渠道

- **GitHub Issues**: https://github.com/hsliuping/TradingAgents-CN/issues
- **QQ群**: 782124367
- **邮箱**: hsliup@163.com

### 社区资源

- **文档**: docs/v1.0.0-preview/
- **示例**: examples/
- **测试**: tests/

---

## 🎉 开始使用

恭喜！你已经成功部署了TradingAgents-CN v1.0.0-preview。

现在你可以：

1. ✅ 分析任意A股/港股/美股
2. ✅ 使用AI生成专业投资报告
3. ✅ 筛选符合条件的股票
4. ✅ 导出和分享分析结果

**祝你投资顺利！** 🚀📈

---

**版本**: v1.0.0-preview  
**更新日期**: 2025-10-15  
**维护者**: TradingAgents-CN Team

