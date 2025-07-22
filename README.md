# TradingAgents 中文增强版

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-cn--0.1.10-green.svg)](./VERSION)
[![Documentation](https://img.shields.io/badge/docs-中文文档-green.svg)](./docs/)
[![Original](https://img.shields.io/badge/基于-TauricResearch/TradingAgents-orange.svg)](https://github.com/TauricResearch/TradingAgents)

> 🚀 **最新版本 cn-0.1.10**: 全新实时进度显示、智能会话管理、异步进度跟踪，Web界面体验全面升级！
>
> 🎯 **核心功能**: Docker容器化部署 | 专业报告导出 | DeepSeek V3集成 | 完整A股支持 | 中文本地化

基于多智能体大语言模型的**中文金融交易决策框架**。专为中文用户优化，提供完整的A股/港股/美股分析能力。

## 🙏 致敬源项目

感谢 [Tauric Research](https://github.com/TauricResearch) 团队创造的革命性多智能体交易框架 [TradingAgents](https://github.com/TauricResearch/TradingAgents)！

**🎯 我们的使命**: 为中国用户提供完整的中文化体验，支持A股/港股市场，集成国产大模型，推动AI金融技术在中文社区的普及应用。

## 🆕 v0.1.10 重大更新

### 🚀 实时进度显示系统
- **异步进度跟踪**: 全新AsyncProgressTracker，实时显示分析进度和步骤
- **智能时间计算**: 修复时间显示问题，准确反映真实分析耗时
- **多种显示模式**: 支持Streamlit、静态、统一等多种进度显示方式

### 📊 智能会话管理
- **状态持久化**: 支持页面刷新后恢复分析状态和历史报告
- **自动降级机制**: Redis不可用时自动切换到文件存储
- **一键查看报告**: 分析完成后显示"📊 查看分析报告"按钮

### 🎨 用户体验优化
- **界面简化**: 移除重复按钮，功能集中化，视觉层次更清晰
- **响应式设计**: 改进移动端适配和不同屏幕尺寸支持
- **错误处理**: 增强异常处理和用户友好的错误提示

## 🎯 核心特性

### 🤖 多智能体协作架构
- **专业分工**: 基本面、技术面、新闻面、社交媒体四大分析师
- **结构化辩论**: 看涨/看跌研究员进行深度分析
- **智能决策**: 交易员基于所有输入做出最终投资建议
- **风险管理**: 多层次风险评估和管理机制

## 🎯 功能特性

### 🚀 Web界面体验 ✨ **v0.1.10全新升级**

| 功能特性 | 状态 | 详细说明 |
|---------|------|----------|
| **📊 实时进度显示** | 🆕 v0.1.10 | 异步进度跟踪，智能步骤识别，准确时间计算 |
| **💾 智能会话管理** | 🆕 v0.1.10 | 状态持久化，自动降级，跨页面恢复 |
| **🎯 一键查看报告** | 🆕 v0.1.10 | 分析完成后一键查看，智能结果恢复 |
| **🎨 界面优化** | 🆕 v0.1.10 | 移除重复按钮，响应式设计，视觉层次优化 |
| **🖥️ Streamlit界面** | ✅ 完整支持 | 现代化响应式界面，实时交互和数据可视化 |
| **⚙️ 配置管理** | ✅ 完整支持 | Web端API密钥管理，模型选择，参数配置 |

### 🎨 CLI用户体验 ✨ **v0.1.9优化**

| 功能特性 | 状态 | 详细说明 |
|---------|------|----------|
| **🖥️ 界面与日志分离** | ✅ 完整支持 | 用户界面清爽美观，技术日志独立管理 |
| **🔄 智能进度显示** | ✅ 完整支持 | 多阶段进度跟踪，防止重复提示 |
| **⏱️ 时间预估功能** | ✅ 完整支持 | 智能分析阶段显示预计耗时 |
| **🌈 Rich彩色输出** | ✅ 完整支持 | 彩色进度指示，状态图标，视觉效果提升 |

### 🧠 LLM模型支持

| 模型提供商 | 支持模型 | 特色功能 |
|-----------|----------|----------|
| **🇨🇳 阿里百炼** | qwen-turbo/plus/max | 中文优化，成本效益高 |
| **🇨🇳 DeepSeek** | deepseek-chat | 工具调用，性价比极高 |
| **🌍 Google AI** | gemini-2.0-flash/1.5-pro | 多模态支持，推理能力强 |
| **🤖 OpenAI** | GPT-4o/4o-mini/3.5-turbo | 通用能力强，生态完善 |

### 📊 数据源与市场

| 市场类型 | 数据源 | 覆盖范围 |
|---------|--------|----------|
| **🇨🇳 A股** | Tushare, AkShare, 通达信 | 沪深两市，实时行情，财报数据 |
| **🇭🇰 港股** | AkShare, Yahoo Finance | 港交所，实时行情，基本面 |
| **🇺🇸 美股** | FinnHub, Yahoo Finance | NYSE, NASDAQ，实时数据 |
| **📰 新闻** | Google News | 实时新闻，多语言支持 |

### 🤖 智能体团队

**分析师团队**: 📈市场分析 | 💰基本面分析 | 📰新闻分析 | 💬情绪分析
**研究团队**: 🐂看涨研究员 | 🐻看跌研究员 | 🎯交易决策员
**管理层**: 🛡️风险管理员 | 👔研究主管

## 🚀 快速开始

### 🐳 Docker部署 (推荐)

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入API密钥

# 3. 启动服务
docker-compose up -d --build

# 4. 访问应用
# Web界面: http://localhost:8501
```

### 💻 本地部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用
python start_web.py

# 3. 访问 http://localhost:8501
```

### 📊 开始分析

1. **选择模型**: DeepSeek V3 / 通义千问 / Gemini
2. **输入股票**: `000001` (A股) / `AAPL` (美股) / `0700.HK` (港股)
3. **开始分析**: 点击"🚀 开始分析"按钮
4. **实时跟踪**: 观察实时进度和分析步骤
5. **查看报告**: 点击"📊 查看分析报告"按钮
6. **导出报告**: 支持Word/PDF/Markdown格式

## 🎯 核心优势

- **🆕 实时进度**: v0.1.10新增异步进度跟踪，告别黑盒等待
- **💾 智能会话**: 状态持久化，页面刷新不丢失分析结果
- **🇨🇳 中国优化**: A股/港股数据 + 国产LLM + 中文界面
- **🐳 容器化**: Docker一键部署，环境隔离，快速扩展
- **📄 专业报告**: 多格式导出，自动生成投资建议
- **🛡️ 稳定可靠**: 多层数据源，智能降级，错误恢复

## 🔧 技术架构

**核心技术**: Python 3.10+ | LangChain | Streamlit | MongoDB | Redis
**AI模型**: DeepSeek V3 | 阿里百炼 | Google AI | OpenAI
**数据源**: Tushare | AkShare | FinnHub | Yahoo Finance
**部署**: Docker | Docker Compose | 本地部署

## 📚 文档和支持

- **📖 完整文档**: [docs/](./docs/) - 安装指南、使用教程、API文档
- **🚨 故障排除**: [troubleshooting/](./docs/troubleshooting/) - 常见问题解决方案
- **🔄 更新日志**: [CHANGELOG.md](./docs/releases/CHANGELOG.md) - 详细版本历史
- **🚀 快速开始**: [QUICKSTART.md](./QUICKSTART.md) - 5分钟快速部署指南

## 🆚 中文增强特色

**相比原版新增**: 实时进度显示 | 智能会话管理 | 中文界面 | A股数据 | 国产LLM | Docker部署 | 专业报告导出 | 统一日志管理 | Web配置界面 | 成本优化

**Docker部署包含的服务**:

- 🌐 **Web应用**: TradingAgents-CN主程序
- 🗄️ **MongoDB**: 数据持久化存储
- ⚡ **Redis**: 高速缓存
- 📊 **MongoDB Express**: 数据库管理界面
- 🎛️ **Redis Commander**: 缓存管理界面

#### 💻 方式二：本地部署

**适用场景**: 开发环境、自定义配置、离线使用

### 环境要求

- Python 3.10+ (推荐 3.11)
- 4GB+ RAM (推荐 8GB+)
- 稳定的网络连接

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 创建虚拟环境
python -m venv env
# Windows
env\Scripts\activate
# Linux/macOS
source env/bin/activate

# 3. 安装所有依赖
pip install -r requirements.txt

# 注意：requirements.txt已包含所有必需依赖：
# - 数据库支持 (MongoDB + Redis)
# - 多市场数据源 (Tushare, AKShare, FinnHub等)
# - Web界面和报告导出功能
```

### 配置API密钥

#### 🇨🇳 推荐：使用阿里百炼（国产大模型）

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，配置以下必需的API密钥：
DASHSCOPE_API_KEY=your_dashscope_api_key_here
FINNHUB_API_KEY=your_finnhub_api_key_here

# 推荐：Tushare API（专业A股数据）
TUSHARE_TOKEN=your_tushare_token_here
TUSHARE_ENABLED=true

# 可选：其他AI模型API
GOOGLE_API_KEY=your_google_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 数据库配置（可选，提升性能）
# 本地部署使用标准端口
MONGODB_ENABLED=false  # 设为true启用MongoDB
REDIS_ENABLED=false    # 设为true启用Redis
MONGODB_HOST=localhost
MONGODB_PORT=27017     # 标准MongoDB端口
REDIS_HOST=localhost
REDIS_PORT=6379        # 标准Redis端口

# Docker部署时需要修改主机名
# MONGODB_HOST=mongodb
# REDIS_HOST=redis
```

#### 📋 部署模式配置说明

**本地部署模式**：

```bash
# 数据库配置（本地部署）
MONGODB_ENABLED=true
REDIS_ENABLED=true
MONGODB_HOST=localhost      # 本地主机
MONGODB_PORT=27017         # 标准端口
REDIS_HOST=localhost       # 本地主机
REDIS_PORT=6379           # 标准端口
```

**Docker部署模式**：

```bash
# 数据库配置（Docker部署）
MONGODB_ENABLED=true
REDIS_ENABLED=true
MONGODB_HOST=mongodb       # Docker容器服务名
MONGODB_PORT=27017        # 标准端口
REDIS_HOST=redis          # Docker容器服务名
REDIS_PORT=6379          # 标准端口
```

> 💡 **配置提示**：
>
> - 本地部署：需要手动启动MongoDB和Redis服务
> - Docker部署：数据库服务通过docker-compose自动启动
> - 端口冲突：如果本地已有数据库服务，可修改docker-compose.yml中的端口映射

#### 🌍 可选：使用国外模型

```bash
# OpenAI (需要科学上网)
OPENAI_API_KEY=your_openai_api_key

# Anthropic (需要科学上网)
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 🗄️ 数据库配置（MongoDB + Redis）

#### 高性能数据存储支持

本项目支持 **MongoDB** 和 **Redis** 数据库，提供：

- **📊 股票数据缓存**: 减少API调用，提升响应速度
- **🔄 智能降级机制**: MongoDB → API → 本地缓存的多层数据源
- **⚡ 高性能缓存**: Redis缓存热点数据，毫秒级响应
- **🛡️ 数据持久化**: MongoDB存储历史数据，支持离线分析

#### 数据库部署方式

**🐳 Docker部署（推荐）**

如果您使用Docker部署，数据库已自动包含在内：

```bash
# Docker部署会自动启动所有服务，包括：
docker-compose up -d --build
# - Web应用 (端口8501)
# - MongoDB (端口27017)
# - Redis (端口6379)
# - 数据库管理界面 (端口8081, 8082)
```

**💻 本地部署 - 数据库配置**

如果您使用本地部署，可以选择以下方式：

**方式一：仅启动数据库服务**

```bash
# 仅启动 MongoDB + Redis 服务（不启动Web应用）
docker-compose up -d mongodb redis mongo-express redis-commander

# 查看服务状态
docker-compose ps

# 停止服务
docker-compose down
```

**方式二：完全本地安装**

```bash
# 数据库依赖已包含在requirements.txt中，无需额外安装

# 启动 MongoDB (默认端口 27017)
mongod --dbpath ./data/mongodb

# 启动 Redis (默认端口 6379)
redis-server
```

> ⚠️ **重要说明**:
>
> - **🐳 Docker部署**: 数据库自动包含，无需额外配置
> - **💻 本地部署**: 可选择仅启动数据库服务或完全本地安装
> - **📋 推荐**: 使用Docker部署以获得最佳体验和一致性

#### 数据库配置选项

**环境变量配置**（推荐）：

```bash
# MongoDB 配置
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=trading_agents
MONGODB_USERNAME=admin
MONGODB_PASSWORD=your_password

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0
```

**配置文件方式**：

```python
# config/database_config.py
DATABASE_CONFIG = {
    'mongodb': {
        'host': 'localhost',
        'port': 27017,
        'database': 'trading_agents',
        'username': 'admin',
        'password': 'your_password'
    },
    'redis': {
        'host': 'localhost',
        'port': 6379,
        'password': 'your_redis_password',
        'db': 0
    }
}
```

#### 数据库功能特性

**MongoDB 功能**：

- ✅ 股票基础信息存储
- ✅ 历史价格数据缓存
- ✅ 分析结果持久化
- ✅ 用户配置管理
- ✅ 自动数据同步

**Redis 功能**：

- ⚡ 实时价格数据缓存
- ⚡ API响应结果缓存
- ⚡ 会话状态管理
- ⚡ 热点数据预加载
- ⚡ 分布式锁支持

#### 智能降级机制

系统采用多层数据源降级策略，确保高可用性：

```
📊 数据获取流程：
1. 🔍 检查 Redis 缓存 (毫秒级)
2. 📚 查询 MongoDB 存储 (秒级)
3. 🌐 调用通达信API (秒级)
4. 💾 本地文件缓存 (备用)
5. ❌ 返回错误信息
```

**配置降级策略**：

```python
# 在 .env 文件中配置
ENABLE_MONGODB=true
ENABLE_REDIS=true
ENABLE_FALLBACK=true

# 缓存过期时间（秒）
REDIS_CACHE_TTL=300
MONGODB_CACHE_TTL=3600
```

#### 性能优化建议

**生产环境配置**：

```bash
# MongoDB 优化
MONGODB_MAX_POOL_SIZE=50
MONGODB_MIN_POOL_SIZE=5
MONGODB_MAX_IDLE_TIME=30000

# Redis 优化
REDIS_MAX_CONNECTIONS=20
REDIS_CONNECTION_POOL_SIZE=10
REDIS_SOCKET_TIMEOUT=5
```

#### 数据库管理工具

```bash
# 初始化数据库
python scripts/setup/init_database.py

# 系统状态检查
python scripts/validation/check_system_status.py

# 清理缓存工具
python scripts/maintenance/cleanup_cache.py --days 7
```

#### 故障排除

**常见问题解决**：

1. **MongoDB连接失败**

   **Docker部署**：

   ```bash
   # 检查服务状态
   docker-compose logs mongodb

   # 重启服务
   docker-compose restart mongodb
   ```

   **本地部署**：

   ```bash
   # 检查MongoDB进程
   ps aux | grep mongod

   # 重启MongoDB
   sudo systemctl restart mongod  # Linux
   brew services restart mongodb  # macOS
   ```
2. **Redis连接超时**

   ```bash
   # 检查Redis状态
   redis-cli ping

   # 清理Redis缓存
   redis-cli flushdb
   ```
3. **缓存问题**

   ```bash
   # 检查系统状态和缓存
   python scripts/validation/check_system_status.py

   # 清理过期缓存
   python scripts/maintenance/cleanup_cache.py --days 7
   ```

> 💡 **提示**: 即使不配置数据库，系统仍可正常运行，会自动降级到API直接调用模式。数据库配置是可选的性能优化功能。

> 📚 **详细文档**: 更多数据库配置信息请参考 [数据库架构文档](docs/architecture/database-architecture.md)

### 📤 报告导出功能

#### 新增功能：专业分析报告导出

本项目现已支持将股票分析结果导出为多种专业格式：

**支持的导出格式**：

- **📄 Markdown (.md)** - 轻量级标记语言，适合技术用户和版本控制
- **📝 Word (.docx)** - Microsoft Word文档，适合商务报告和进一步编辑
- **📊 PDF (.pdf)** - 便携式文档格式，适合正式分享和打印

**报告内容结构**：

- 🎯 **投资决策摘要** - 买入/持有/卖出建议，置信度，风险评分
- 📊 **详细分析报告** - 技术分析，基本面分析，市场情绪，新闻事件
- ⚠️ **风险提示** - 完整的投资风险声明和免责条款
- 📋 **配置信息** - 分析参数，模型信息，生成时间

**使用方法**：

1. 完成股票分析后，在结果页面底部找到"📤 导出报告"部分
2. 选择需要的格式：Markdown、Word或PDF
3. 点击导出按钮，系统自动生成并提供下载

**安装导出依赖**：

```bash
# 安装Python依赖
pip install markdown pypandoc

# 安装系统工具（用于PDF导出）
# Windows: choco install pandoc wkhtmltopdf
# macOS: brew install pandoc wkhtmltopdf
# Linux: sudo apt-get install pandoc wkhtmltopdf
```

> 📚 **详细文档**: 完整的导出功能使用指南请参考 [导出功能指南](docs/EXPORT_GUIDE.md)

### 🚀 启动应用

#### 🐳 Docker启动（推荐）

如果您使用Docker部署，应用已经自动启动：

```bash
# 应用已在Docker中运行，直接访问：
# Web界面: http://localhost:8501
# 数据库管理: http://localhost:8081
# 缓存管理: http://localhost:8082

# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f web
```

#### 💻 本地启动

如果您使用本地部署：

```bash
# 1. 激活虚拟环境
# Windows
.\env\Scripts\activate
# Linux/macOS
source env/bin/activate

# 2. 安装项目到虚拟环境（重要！）
pip install -e .

# 3. 启动Web管理界面
# 方法1：使用项目启动脚本（推荐）
python start_web.py

# 方法2：使用原始启动脚本
python web/run_web.py

# 方法3：直接使用streamlit（需要先安装项目）
streamlit run web/app.py
```

然后在浏览器中访问 `http://localhost:8501`

**Web界面特色功能**:

- 🇺🇸 **美股分析**: 支持 AAPL, TSLA, NVDA 等美股代码
- 🇨🇳 **A股分析**: 支持 000001, 600519, 300750 等A股代码
- 📊 **实时数据**: 通达信API提供A股实时行情数据
- 🤖 **智能体选择**: 可选择不同的分析师组合
- 📤 **报告导出**: 一键导出Markdown/Word/PDF格式专业分析报告
- 🎯 **5级研究深度**: 从快速分析(2-4分钟)到全面分析(15-25分钟)
- 📊 **智能分析师选择**: 市场技术、基本面、新闻、社交媒体分析师
- 🔄 **实时进度显示**: 可视化分析过程，避免等待焦虑
- 📈 **结构化结果**: 投资建议、目标价位、置信度、风险评估
- 🇨🇳 **完全中文化**: 界面和分析结果全中文显示

**研究深度级别说明**:

- **1级 - 快速分析** (2-4分钟): 日常监控，基础决策
- **2级 - 基础分析** (4-6分钟): 常规投资，平衡速度
- **3级 - 标准分析** (6-10分钟): 重要决策，推荐默认
- **4级 - 深度分析** (10-15分钟): 重大投资，详细研究
- **5级 - 全面分析** (15-25分钟): 最重要决策，最全面分析

#### 💻 代码调用（适合开发者）

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# 配置阿里百炼
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"
config["deep_think_llm"] = "qwen-plus"      # 深度分析
config["quick_think_llm"] = "qwen-turbo"    # 快速任务

# 创建交易智能体
ta = TradingAgentsGraph(debug=True, config=config)

# 分析股票 (以苹果公司为例)
state, decision = ta.propagate("AAPL", "2024-01-15")

# 输出分析结果
print(f"推荐动作: {decision['action']}")
print(f"置信度: {decision['confidence']:.1%}")
print(f"风险评分: {decision['risk_score']:.1%}")
print(f"推理过程: {decision['reasoning']}")
```

#### 快速启动脚本

```bash
# 阿里百炼演示（推荐中文用户）
python examples/dashscope/demo_dashscope_chinese.py

# 阿里百炼完整演示
python examples/dashscope/demo_dashscope.py

# 阿里百炼简化测试
python examples/dashscope/demo_dashscope_simple.py

# OpenAI演示（需要国外API）
python examples/openai/demo_openai.py

# 集成测试
python tests/integration/test_dashscope_integration.py
```

#### 📁 数据目录配置

**新功能**: 灵活配置数据存储路径，支持多种配置方式：

```bash
# 查看当前数据目录配置
python -m cli.main data-config --show

# 设置自定义数据目录
python -m cli.main data-config --set /path/to/your/data

# 重置为默认配置
python -m cli.main data-config --reset
```

**环境变量配置**:

```bash
# Windows
set TRADING_AGENTS_DATA_DIR=C:\MyTradingData

# Linux/macOS
export TRADING_AGENTS_DATA_DIR=/home/user/trading_data
```

**程序化配置**:

```python
from tradingagents.config_manager import ConfigManager

# 设置数据目录
config_manager = ConfigManager()
config_manager.set_data_directory("/path/to/data")

# 获取配置
data_dir = config_manager.get_data_directory()
print(f"数据目录: {data_dir}")
```

**配置优先级**: 程序设置 > 环境变量 > 配置文件 > 默认值

详细说明请参考: [📁 数据目录配置指南](docs/configuration/data-directory-configuration.md)

### 交互式分析

```bash
# 启动交互式命令行界面
python -m cli.main
```

## 🎯 **快速导航** - 找到您需要的内容


| 🎯**I want to...** | 📖**Recommended Documentation**                                            | ⏱️**Reading Time** |
| --------------- | --------------------------------------------------------- | ---------------- |
| **Quick Start**    | [🚀 Quick Start](docs/overview/quick-start.md)               | 10 minutes           |
| **Understand Architecture**    | [🏛️ System Architecture](docs/architecture/system-architecture.md) | 15 minutes           |
| **Look at Code Examples**  | [📚 Basic Examples](docs/examples/basic-examples.md)            | 20 minutes           |
| **Solve Problems**    | [�� Common Questions](docs/faq/faq.md)                            | 5 minutes            |
| **Deep Learning**  | [📁 Complete Document Directory](#-Complete Document Directory)                         | 2 hours+           |

> 💡 **Hint**: Our `docs/` directory contains **50,000+ words** of detailed Chinese documentation, which is the biggest difference from the original version!

## 📚 Complete Document System - Core Highlights

> **🌟 This is the biggest difference from the original version!** We have built the most complete Chinese financial AI framework documentation system, including more than **50,000 words** of detailed technical documentation, **20+** professional document files, **100+** code examples.

### Why Choose Our Documentation?


| Dimension     | Original TradingAgents | 🚀**Chinese Enhanced Version**           |
| ------------ | ------------------ | -------------------------- |
| **Documentation Language** | English basic description | **Complete Chinese system**           |
| **Documentation Depth** | Simple introduction | **Deep technical analysis**           |
| **Architecture Description** | Conceptual description | **Detailed design documents + architecture diagrams**  |
| **Usage Guide** | Basic examples | **Complete path from beginner to expert** |
| **Troubleshooting** | None | **Detailed FAQ + solutions**     |
| **Code Examples** | Few examples | **100+ Practical Examples**          |

### 📖 Document Navigation - Organized by Learning Path

#### 🚀 **Newbie Path** (Recommended to start from here)

1. [📋 Project Overview](docs/overview/project-overview.md) - **Understand the project background and core value**
2. [⚙️ Detailed Installation](docs/overview/installation.md) - **Detailed installation guides for all platforms**
3. [🚀 Quick Start](docs/overview/quick-start.md) - **10-minute guide**
4. [📚 Basic Examples](docs/examples/basic-examples.md) - **8 practical beginner examples**

#### 🏗️ **Architecture Understanding Path** (Deepen your understanding of system design)

1. [🏛️ System Architecture](docs/architecture/system-architecture.md) - **Complete system architecture design**
2. [🤖 Agent Architecture](docs/architecture/agent-architecture.md) - **Multi-agent collaboration mechanism**
3. [📊 Data Flow Architecture](docs/architecture/data-flow-architecture.md) - **Complete data processing workflow**
4. [🔄 Graph Structure Design](docs/architecture/graph-structure.md) - **LangGraph workflow**

#### 🤖 **Agent Deep Analysis** (Understand the design of each agent)

1. [📈 Analyst Team](docs/agents/analysts.md) - **Detailed explanation of four professional analysts**
2. [🔬 Researcher Team](docs/agents/researchers.md) - **Bullish/Bearish debate mechanism**
3. [💼 Trader Agent](docs/agents/trader.md) - **Trading decision-making process**
4. [🛡️ Risk Management](docs/agents/risk-management.md) - **Multi-level risk assessment**
5. [👔 Manager Agent](docs/agents/managers.md) - **Coordination and decision management**

#### 📊 **Data Processing Specialization** (Master data processing technology)

1. [🔌 Data Source Integration](docs/data/data-sources.md) - **Multi-data source API integration**
2. [⚙️ Data Processing Flow](docs/data/data-processing.md) - **Data cleaning and conversion**
3. [💾 Cache Strategy](docs/data/caching.md) - **Multi-layer cache optimization performance**

#### ⚙️ **Configuration and Optimization** (Performance tuning and customization)

1. [📝 Configuration Guide](docs/configuration/config-guide.md) - **Detailed configuration option description**
2. [🧠 LLM Configuration](docs/configuration/llm-config.md) - **Large language model optimization**

#### 💡 **Advanced Applications** (Extend development and practice)

1. [📚 Basic Examples](docs/examples/basic-examples.md) - **8 practical basic examples**
2. [🚀 Advanced Examples](docs/examples/advanced-examples.md) - **Complex scenarios and extended development**

#### ❓ **Problem Solving** (Check when you encounter problems)

1. [🆘 Common Questions](docs/faq/faq.md) - **Detailed FAQ and solutions**

### 📊 Document Statistics

- 📄 **Document Files**: 20+ professional documents
- 📝 **Total Words**: 50,000+ detailed content
- 💻 **Code Examples**: 100+ practical examples
- 📈 **Architecture Diagrams**: 10+ professional diagrams
- 🎯 **Coverage**: Complete path from beginner to expert

### 🎨 Document Features

- **🇨🇳 Fully Chinese**: Expressions optimized for Chinese users
- **📊 Rich Illustrations**: Rich architecture diagrams and flowcharts
- **💻 Rich Code**: Each concept has a corresponding code example
- **🔍 Deep Analysis**: Not only tells you how to do it, but also why it's done this way
- **🛠️ Practical Orientation**: All documents are oriented to practical application scenarios

---

## 📚 Complete Document Directory

### 📁 **docs/ Directory Structure** - Complete Knowledge System

```
docs/
├── 📖 overview/              # Project Overview - Newbie Must Read
│   ├── project-overview.md   # 📋 Detailed project introduction
│   ├── quick-start.md        # 🚀 10-minute quick start
│   └── installation.md       # ⚙️ Detailed installation guide
│
├── 🏗️ architecture/          # System Architecture - Deep Understanding
│   ├── system-architecture.md    # 🏛️ Overall architecture design
│   ├── agent-architecture.md     # 🤖 Agent collaboration mechanism
│   ├── data-flow-architecture.md # 📊 Data processing architecture
│   └── graph-structure.md        # 🔄 LangGraph workflow
│
├── 🤖 agents/               # Agent Deep Analysis - Core Components
│   ├── analysts.md          # 📈 Four professional analysts
│   ├── researchers.md       # 🔬 Bullish/Bearish debate mechanism
│   ├── trader.md           # 💼 Trading decision-making
│   ├── risk-management.md  # 🛡️ Multi-level risk assessment
│   └── managers.md         # 👔 Manager coordination
│
├── 📊 data/                 # Data Processing - Technical Core
│   ├── data-sources.md      # 🔌 Multi-data source integration
│   ├── data-processing.md   # ⚙️ Data processing flow
│   └── caching.md          # 💾 Cache optimization strategy
│
├── ⚙️ configuration/        # Configuration Optimization - Performance Tuning
│   ├── config-guide.md      # 📝 Detailed configuration instructions
│   └── llm-config.md       # 🧠 LLM model optimization
│
├── 💡 examples/             # Example Tutorials - Practical Applications
│   ├── basic-examples.md    # 📚 8 basic examples
│   └── advanced-examples.md # 🚀 Advanced development examples
│
└── ❓ faq/                  # Problem Solving - Troubleshooting
    └── faq.md              # 🆘 Common questions FAQ
```

### 🎯 **Key Recommended Documents** (Must-read精选)

#### 🔥 **Most Popular Documents**

1. **[📋 Project Overview](docs/overview/project-overview.md)** - ⭐⭐⭐⭐⭐

   > Understand the core value and technical features of the project, 5 minutes to understand the entire framework
   >
2. **[🏛️ System Architecture](docs/architecture/system-architecture.md)** - ⭐⭐⭐⭐⭐

   > Deeply analyze the multi-agent collaboration mechanism, including detailed architecture diagrams
   >
3. **[📚 Basic Examples](docs/examples/basic-examples.md)** - ⭐⭐⭐⭐⭐

   > 8 practical examples, from stock analysis to portfolio optimization
   >

#### 🚀 **Technical Depth Documents**

1. **[�� Agent Architecture](docs/architecture/agent-architecture.md)**

   > Detailed explanation of multi-agent design patterns and collaboration mechanisms
   >
2. **[📊 Data Flow Architecture](docs/architecture/data-flow-architecture.md)**

   > Complete process of data acquisition, processing, and caching
   >
3. **[🔬 Researcher Team](docs/agents/researchers.md)**

   > Innovative design of bullish/bearish debate mechanism
   >

#### 💼 **Utility Tools Documentation**

1. **[🌐 Web Interface Guide](docs/usage/web-interface-guide.md)** - ⭐⭐⭐⭐⭐

   > Complete Web interface usage tutorial, including 5-level research depth detailed instructions
   >
2. **[💰 Investment Analysis Guide](docs/usage/investment_analysis_guide.md)**

   > Complete investment analysis tutorial from basic to advanced
   >
3. **[🧠 LLM Configuration](docs/configuration/llm-config.md)**

   > Multi-LLM model configuration and cost optimization strategy
   >
4. **[💾 Cache Strategy](docs/data/caching.md)**

   > Multi-layer cache design, significantly reducing API call costs
   >
5. **[🆘 Common Questions](docs/faq/faq.md)**

   > Detailed FAQ and troubleshooting guide
   >

### 📖 **Browse Documents by Module**

<details>
<summary><strong>📖 Overview Documentation</strong> - Project Introduction Must Read</summary>

- [📋 Project Overview](docs/overview/project-overview.md) - Detailed project background and feature introduction
- [🚀 Quick Start](docs/overview/quick-start.md) - Complete guide from installation to first run
- [⚙️ Detailed Installation](docs/overview/installation.md) - Detailed installation instructions for all platforms

</details>

<details>
<summary><strong>🏗️ Architecture Documentation</strong> - Deep Understanding of System Design</summary>

- [🏛️ System Architecture](docs/architecture/system-architecture.md) - Complete system architecture design
- [🤖 Agent Architecture](docs/architecture/agent-architecture.md) - Agent design patterns and collaboration mechanisms
- [📊 Data Flow Architecture](docs/architecture/data-flow-architecture.md) - Data acquisition, processing, and distribution process
- [🔄 Graph Structure Design](docs/architecture/graph-structure.md) - LangGraph workflow design

</details>

<details>
<summary><strong>🤖 Agent Documentation</strong> - Core Component Deep Analysis</summary>

- [📈 Analyst Team](docs/agents/analysts.md) - Detailed explanation of four professional analysts
- [🔬 Researcher Team](docs/agents/researchers.md) - Bullish/Bearish debate mechanism and research team
- [💼 Trader Agent](docs/agents/trader.md) - Trading decision-making process
- [🛡️ Risk Management](docs/agents/risk-management.md) - Multi-level risk assessment system
- [👔 Manager Agent](docs/agents/managers.md) - Coordination and decision management

</details>

<details>
<summary><strong>📊 Data Processing</strong> - Technical Core Implementation</summary>

- [🔌 Data Source Integration](docs/data/data-sources.md) - Supported data sources and API integration
- [⚙️ Data Processing Flow](docs/data/data-processing.md) - Data cleaning, conversion, and verification
- [💾 Cache Strategy](docs/data/caching.md) - Multi-layer cache optimization performance

</details>

<details>
<summary><strong>⚙️ Configuration and Deployment</strong> - Performance Tuning Guide</summary>

- [📝 Configuration Guide](docs/configuration/config-guide.md) - Detailed configuration option description
- [🧠 LLM Configuration](docs/configuration/llm-config.md) - Large language model optimization

</details>

<details>
<summary><strong>💡 Examples and Tutorials</strong> - Practical Application Guide</summary>

- [📚 Basic Examples](docs/examples/basic-examples.md) - 8 practical basic examples
- [🚀 Advanced Examples](docs/examples/advanced-examples.md) - Complex scenarios and extended development

</details>

<details>
<summary><strong>❓ Help Documentation</strong> - Problem Solutions</summary>

- [🆘 Common Questions](docs/faq/faq.md) - Detailed FAQ and solutions

</details>

## 💰 Cost Control

### Typical Usage Costs

- **Economy Mode**: $0.01-0.05/analysis (using gpt-4o-mini)
- **Standard Mode**: $0.05-0.15/analysis (using gpt-4o)
- **High Precision Mode**: $0.10-0.30/analysis (using gpt-4o + multi-round debate)

### Cost Optimization Suggestions

```python
# Low-cost configuration example
cost_optimized_config = {
    "deep_think_llm": "gpt-4o-mini",
    "quick_think_llm": "gpt-4o-mini", 
    "max_debate_rounds": 1,
    "online_tools": False  # Use cached data
}
```

## 🤝 Contribution Guidelines

We welcome various forms of contributions:

### Contribution Types

- 🐛 **Bug Fixes** - Find and fix issues
- ✨ **New Features** - Add new features
- 📚 **Documentation Improvements** - Improve documentation and tutorials
- 🌐 **Localization** - Translation and localization work
- 🎨 **Code Optimization** - Performance optimization and code refactoring

### Contribution Process

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Create a Pull Request

## 📄 License

This project is open source under the Apache 2.0 license. See [LICENSE](LICENSE) file.

### License Explanation

- ✅ Commercial use
- ✅ Modification and distribution
- ✅ Private use
- ✅ Patent use
- ❗ Need to retain copyright notice
- ❗ Need to include license copy

## 🙏 Acknowledgments and Gratitude

### 🌟 Tribute to Source Project Developers

We express the deepest respect and gratitude to the [Tauric Research](https://github.com/TauricResearch) team:

- **🎯 Vision Leader**: Thank you for your visionary thinking and innovative practices in the AI financial field
- **💎 Precious Source Code**: Thank you for every line of open-source code, which embodies countless wisdom and hard work
- **🏗️ Architecture Master**: Thank you for designing such an elegant, scalable multi-agent framework
- **💡 Technical Pioneer**: Thank you for perfectly combining cutting-edge AI technology with financial practice
- **🔄 Continuous Contribution**: Thank you for continuous maintenance, updates, and improvements

### 🤝 Community Contributors

Thank you to the following community contributors for their important contributions to the TradingAgents-CN project:

#### 🐳 Docker Containerization

- **[@breeze303](https://github.com/breeze303)**: Provided complete Docker Compose configuration and containerization deployment solution, greatly simplifying project deployment and development environment configuration

#### 📄 Report Export Function

- **[@baiyuxiong](https://github.com/baiyuxiong)** (baiyuxiong@163.com): Designed and implemented a complete multi-format report export system, including Word, PDF, Markdown format support

#### 🌟 Other Contributions

- **All users who submitted issues**: Thank you for your issue feedback and feature suggestions
- **Test users**: Thank you for your testing and feedback during development
- **Documentation contributors**: Thank you for improving and refining project documentation
- **🌍 Open Source Contribution**: Thank you for choosing the Apache 2.0 protocol, giving developers the greatest freedom
- **📚 Knowledge Sharing**: Thank you for providing detailed documentation and best practice guidance

**Special Thanks**: [TradingAgents](https://github.com/TauricResearch/TradingAgents) project provided us with a solid technical foundation. Although the Apache 2.0 protocol grants us the right to use the source code, we deeply understand the precious value of every line of code and will always remember and thank you for your selfless contributions.

### 🇨🇳 Promotion Mission

We created this Chinese enhanced version with the following motivations:

- **🌉 Technology Spread**: Let excellent TradingAgents technology be more widely applied in China
- **🎓 Education Popularization**: Provide better tools and resources for Chinese AI financial education
- **🤝 Cultural Bridge**: Build a bridge for communication and cooperation between Chinese and Western technical communities
- **🚀 Innovation Promotion**: Promote AI technological innovation and application in the Chinese financial technology field

### 🌍 Open Source Community

Thank you to all developers and users who contributed code, documentation, suggestions, and feedback to this project. Because of your support, we can better serve the Chinese user community.

### 🤝 Win-win Cooperation

We promise:

- **Respect Originality**: Always respect the intellectual property rights and open source agreements of the source project
- **Feedback Contribution**: Will provide valuable improvements and innovations to the source project and open source community
- **Continuous Improvement**: Continuously improve the Chinese enhanced version to provide a better user experience
- **Open Cooperation**: Welcome to technical exchanges and cooperation with the source project team and global developers

## 📈 Version History

- **v0.1.10** (2025-07-18): 🚀 Web interface real-time progress display and intelligent session management ✨ **Latest Version**
- **v0.1.9** (2025-07-16): 🎯 CLI user experience major optimization and unified log management
- **v0.1.8** (2025-07-15): 🎨 Web interface comprehensive optimization and user experience improvement
- **v0.1.7** (2025-07-13): 🐳 Containerized deployment and professional report export
- **v0.1.6** (2025-07-11): 🔧 Ali Baiyan repair and data source upgrade
- **v0.1.5** (2025-07-08): 📊 Add Deepseek model support
- **v0.1.4** (2025-07-05): 🏗️ Architecture optimization and configuration management reconstruction
- **v0.1.3** (2025-06-28): 🇨🇳 A-share market full support
- **v0.1.2** (2025-06-15): 🌐 Web interface and configuration management
- **v0.1.1** (2025-06-01): 🧠 Domestic LLM integration

📋 **Detailed Update Log**: [CHANGELOG.md](./docs/releases/CHANGELOG.md)

## 📞 Contact Information

- **GitHub Issues**: [Submit Issues and Suggestions](https://github.com/hsliuping/TradingAgents-CN/issues)
- **Email**: hsliup@163.com
- **Original Project**: [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- **Documentation**: [Complete Document Directory](docs/)

## ⚠️ Risk Warning

**Important Statement**: This framework is only for research and education purposes, not investment advice.

- 📊 Trading performance may vary due to various factors
- 🤖 AI model predictions are uncertain
- 💰 Investment carries risks, decision-making needs to be cautious
- 👨‍💼 It is recommended to consult professional financial advisors

---

<div align="center">

**🌟 If this project helps you, please give us a Star!**

[⭐ Star this repo](https://github.com/hsliuping/TradingAgents-CN) | [🍴 Fork this repo](https://github.com/hsliuping/TradingAgents-CN/fork) | [📖 Read the docs](./docs/)

</div>
