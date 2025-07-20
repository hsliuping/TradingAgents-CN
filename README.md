# TradingAgents 中文增强版

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-cn--0.1.10-green.svg)](./VERSION)
[![Documentation](https://img.shields.io/badge/docs-中文文档-green.svg)](./docs/)
[![Original](https://img.shields.io/badge/基于-TauricResearch/TradingAgents-orange.svg)](https://github.com/TauricResearch/TradingAgents)

> 🚀 **最新版本 cn-0.1.10**: 全新实时进度显示、智能会话管理、异步进度跟踪，Web界面体验全面升级！
>
> 🎯 **核心功能**: 专业报告导出 | DeepSeek V3集成 | 完整A股支持 | 中文本地化 | 本地化开发

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

### 💻 本地部署

#### 环境要求

- Python 3.10+ (推荐 3.11)
- 4GB+ RAM (推荐 8GB+)
- 稳定的网络连接

#### 安装步骤

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

#### 配置API密钥

##### 🇨🇳 推荐：使用阿里百炼（国产大模型）

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
MONGODB_ENABLED=false  # 设为true启用MongoDB
REDIS_ENABLED=false    # 设为true启用Redis
MONGODB_HOST=localhost
MONGODB_PORT=27017     # 标准MongoDB端口
REDIS_HOST=localhost
REDIS_PORT=6379        # 标准Redis端口
```

##### 🌍 可选：使用国外模型

```bash
# OpenAI (需要科学上网)
OPENAI_API_KEY=your_openai_api_key

# Anthropic (需要科学上网)
ANTHROPIC_API_KEY=your_anthropic_api_key
```

#### 启动应用

```bash
# 确保虚拟环境已激活
# 启动Web界面
python start_web.py

# 或使用 Streamlit 直接启动
streamlit run web/app.py

# 访问 http://localhost:8501
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
- **💻 本地开发**: 纯本地部署，无Docker依赖，便于研究开发
- **📄 专业报告**: 多格式导出，自动生成投资建议
- **🛡️ 稳定可靠**: 多层数据源，智能降级，错误恢复

## 🔧 技术架构

**核心技术**: Python 3.10+ | LangChain | Streamlit | MongoDB | Redis
**AI模型**: DeepSeek V3 | 阿里百炼 | Google AI | OpenAI
**数据源**: Tushare | AkShare | FinnHub | Yahoo Finance
**部署**: 本地部署 | 虚拟环境

## 🗄️ 数据库配置（可选）

### 高性能数据存储支持

本项目支持 **MongoDB** 和 **Redis** 数据库，提供：

- **📊 股票数据缓存**: 减少API调用，提升响应速度
- **🔄 智能降级机制**: MongoDB → API → 本地缓存的多层数据源
- **⚡ 高性能缓存**: Redis缓存热点数据，毫秒级响应
- **🛡️ 数据持久化**: MongoDB存储历史数据，支持离线分析

### 本地数据库安装

**MongoDB安装**：

```bash
# Windows: 下载MongoDB Community Server
# https://www.mongodb.com/try/download/community

# macOS:
brew tap mongodb/brew
brew install mongodb-community

# Ubuntu/Debian:
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install mongodb-org
```

**Redis安装**：

```bash
# Windows: 下载Redis for Windows
# https://github.com/microsoftarchive/redis/releases

# macOS:
brew install redis

# Ubuntu/Debian:
sudo apt install redis-server
```

### 数据库启动

```bash
# 启动 MongoDB
mongod --dbpath ./data/mongodb

# 启动 Redis
redis-server

# 在.env文件中启用数据库
MONGODB_ENABLED=true
REDIS_ENABLED=true
```

### 数据库管理工具

```bash
# 初始化数据库
python scripts/setup/init_database.py

# 系统状态检查
python scripts/validation/check_system_status.py

# 清理缓存工具
python scripts/maintenance/cleanup_cache.py --days 7
```

> 💡 **提示**: 即使不配置数据库，系统仍可正常运行，会自动降级到API直接调用模式。数据库配置是可选的性能优化功能。

## 📚 文档和支持

- **📖 完整文档**: [docs/](./docs/) - 安装指南、使用教程、API文档
- **🚨 故障排除**: [troubleshooting/](./docs/troubleshooting/) - 常见问题解决方案
- **🔄 更新日志**: [CHANGELOG.md](./docs/releases/CHANGELOG.md) - 详细版本历史
- **🚀 快速开始**: [overview/quick-start.md](./docs/overview/quick-start.md) - 快速部署指南

## 🆚 中文增强特色

**相比原版新增**: 实时进度显示 | 智能会话管理 | 中文界面 | A股数据 | 国产LLM | 专业报告导出 | 统一日志管理 | Web配置界面 | 成本优化 | 本地开发优化

**适合场景**:

- 🔬 **学术研究**: 纯本地环境，便于代码分析和算法研究
- 💼 **金融机构**: 内网部署，数据安全可控
- 👨‍💻 **个人开发**: 轻量级部署，快速上手
- 🎓 **教学培训**: 简单安装，专注功能学习

## 🚀 CLI使用

```bash
# 启动CLI分析工具
python -m cli.main

# 或使用快速分析
python examples/cli_demo.py
```

## 📊 API使用

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# 创建配置
config = DEFAULT_CONFIG.copy()
config["deep_think_llm"] = "deepseek-chat"
config["quick_think_llm"] = "deepseek-chat"

# 初始化交易智能体图
ta = TradingAgentsGraph(debug=True, config=config)

# 执行分析
state, decision = ta.propagate("AAPL", "2024-01-15")
print(decision)
```

## 🤝 贡献指南

欢迎贡献代码、文档或反馈问题！

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目基于 Apache 2.0 许可证开源。详细信息请查看 [LICENSE](LICENSE) 文件。

## 🙏 致谢

特别感谢以下贡献者和项目：

- **[Tauric Research](https://github.com/TauricResearch)**: 原始TradingAgents框架
- **开源社区**: 各种优秀的Python包和工具
- **中文用户**: 宝贵的反馈和建议

---

**让AI帮您做出更明智的投资决策！** 🚀📈